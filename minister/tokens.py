import eventlet

try:
    import json
except ImportError:
    import simplejson as json

import sys, os
from uuid import uuid4
from service import Service
from resource import Resource
from source import Source
from util import MutableFile, fix_unicode_keys

TOKEN_STATES = {
    "updating":         "Awaiting deployment; the source is updating.",
    "deploying":        "In the process of being deployed.",
    "redeploying":      "In the process of being redeployed.",
    "withdrawing":      "In the process of being withdrawn.",
    "active":           "Actively deployed; things are running smoothly.",
    "struggling":       "Deployed but some processes have failed and cannot restart.",
    "failed":           "Deployment failed; all processes have failed and cannot restart.",
    "disabled":         "Purposefully not deployed; per the 'disabled' setting.",
    "mia":              "Cannot deploy; deployment source is missing.",
}

class ServiceToken(object):
    """
    A ServiceToken acts as a broker, keeping track of a service, deploying it, 
    loading it, etc.
    """

    def __init__(self, manager, path, override=None):
        self.path = path
        self.slug = os.path.basename( os.path.abspath(path) ) or path
        self.manager = manager
        self.service = None
        self.threads = []
        self.status = "failed"
        self.status_info = ""
        self.source = None
        self.deploy_file = None
        self.override = override or {}
        self.override['path'] = self.path
        self.deploy_options = self.override.copy()
        self.deploy_file = None
        self.log = manager.log
        self.call_chain = None
        
    ### Options ###
    def __getitem__(self, k):
        if k in self.override:
            return self.override[k]
        if self.service:
            return getattr(self.service, k)
        elif self.deploy_options:
            return self.deploy_options[k]
        raise IndexError(k)
        
    def get(self, k, default=None):
        if k in self.override:
            return self.override[k]
        elif self.deploy_options:
            return self.deploy_options.get(k, default)
    
    def __setitem__(self, k, v):
        self.override[k] = v
        
    @property
    def disabled(self):
        return self.get('disabled')
        
    ### Methods ###
    def load_options(self):
        if self.path.startswith('@'):
            self.deploy_options = self.override
            return self.deploy_options
            
        path = os.path.join( self.path, 'service.json' )
        if self.deploy_file and not self.deploy_file.is_stale():
            self.deploy_options.update( self.override )
            return self.deploy_options
        if os.path.exists(path):
            try:
                self.deploy_file = MutableFile(path)
                self.deploy_options = fix_unicode_keys( json.load(self.deploy_file) )
            except Exception, e:
                self.log.error("Bad service.json - %s: %s" % (path, e))
                self.deploy_file = None
                self.deploy_options = {}
                self.status = "failed"
                self.status_info = "Bad service.json"
                raise
        else:
            self.deploy_file = None
            self.deploy_options = {}
            self.status = "mia"
            self.status_info = "Path doesn't exist."
            raise RuntimeError("Path does not exist: %s" % path )
        self.deploy_options.update( self.override )
        self.deploy_options.setdefault('name', self.slug)
        return self.deploy_options
    
    def deploy(self):
        if self.service:
            return
        self.threads.append( eventlet.spawn(self._deploy) )
        self.status = 'deploying'
        self.status_info = ""
    
    def _deploy(self):
        if self.deploy_options.get('disabled'):
            self.status = 'disabled'
            return
        
        self.status = 'updating'
        if not self.source:
            source = self.get('source')
            if source:
                typ, _, src = source.partition(":")
                self.source = Source(type=typ, src=src)
        
        if self.source:
            if not self.source.update(self.path):
                self.status = 'mia'
                return
        
        self.status = "deploying"
        
        try:
            options = self.load_options().copy()
            options['_manager'] = self.manager
            options['_logger'] = self.log
        except Exception, e:
            if self.status == 'deploying':
                self.status = 'failed'
                self.status_info = "Error in deployment."
            return
        
        if not options.get('type'):
            self.status = "mia"
            self.status_info = "Service type not found."
            self.log.error("Service lacks service type: %s", self.path)
            return
        
        cls = Resource.get_class(options['type'] + ":service")
        if cls is not None:
            options['type'] = options['type'] + ':service'
        
        else:
            cls = Resource.get_class(options['type'])
            if cls is None:
                self.status = "failed"
                self.status_info = "Cannot find service type: %s" % options['type']
                self.log.error(self.status_info)
                return
        
        try:
            self.service = Resource.create(options)
        except Exception, e:
            self.log.exception(e)
            if self.status == 'deploying':
                self.status = 'failed'
                self.status_info = "Error in deployment."
            return
        
        if self.service.disabled:
            self.status = 'disabled'
        else:
            self.service.start()
            
        self.app = self.service.get_app()
        
        self.threads.append( eventlet.spawn(self._status_loop) )
        self.threads.remove( eventlet.getcurrent() )
    
    def match_path(self, path):
        if not self.service:
            raise RuntimeError("Service not deployed.")
        return self.service.match_path(path)
    
    def match_site(self, hostname):
        if not self.service:
            raise RuntimeError("Service not deployed.")
        return self.service.match_site(hostname)
    
    def check_source(self):
        if self.source:
            return self.source.check(self.path)
        return True
    
    def is_valid(self):
        try:
            options = self.load_options()
        except Exception, e:
            self.status = "failed"
            return False
            
        return (options.get('type', None) is not None)
    
    def withdraw(self):
        self.status = "withdrawing"
        self._withdraw()
        self.status = 'disabled'
    
    def _withdraw(self):
        if self.threads:
            for g in self.threads:
                if g is not eventlet.getcurrent():
                    self.threads.remove(g)
                    eventlet.kill(g)
        
        if self.service:
            self.service.stop()
            self.service = None
        
    def redeploy(self):
        self.status = 'redeploying'
        self._withdraw()
        self.deploy()
    
    def _status_loop(self, interval=0.5):
        while True:
            try:
                if self.deploy_file and self.deploy_file.is_stale():
                    self.log.info("reloading service: %s", self.path)
                    return self.redeploy()
                healthy, info = self.service.get_health()
                if not healthy:
                    self.status = "failed"
                else:
                    self.status = "active"
                    self.status_info = info
            except Exception, e:
                self.log.exception(e)
            eventlet.sleep(interval)
    
    def info(self):
        if (self.service):
            info = self.service.simple()
        else:
            info = self.deploy_options.copy()
        info['status'] = self.status
        if self.status_info != self.status:
            info['statusText'] = self.status_info
        info['name'] = info.get('name', self.slug)
        info['slug'] = self.slug
        info['path'] = self.path
        info['type'] = info.get('type', 'unknown').replace(':service', '')
        return info
    
    def remove(self):
        import shutil
        
        self._withdraw()
        shutil.rmtree(self.path, True)
    
    def simple(self):
        return self.override.copy()
    
    def __call__(self, environ, start_response):
        return self.app(environ, start_response)
        
