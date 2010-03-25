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
    "updating":         "Awaiting deployment, as the source updates.",
    "deploying":        "In the process of being deployed.",
    "redeploying":      "In the process of being redeployed.",
    "withdrawing":      "In the process of being withdrawn.",
    "active":           "Actively deployed, things are running smoothly.",
    "struggling":       "Deployed but some processes have failed and cannot restart.",
    "failed":           "Deployment failed, all processes have failed and cannot restart.",
    "disabled":         "Purposefully not deployed, as per the 'disabled' setting.",
    "mia":              "Cannot Deploy, as deployment source is missing.",
}

class ServiceToken(Resource):
    ### Initialization ###
    def __init__(self, properties=None):
        self.properties = properties
        self.properties['path'] = properties.get('path')
        
        self._service = None
        self._threads = []
        self._status = "building"
        self._extra = ""
        self._config = None
        self._config_file = None
        self._manager = None
        
        src = self.properties.get('src')
        if src:
            type, _, src = src.partition(":")
            self._source = Source(type=type, src=src)
        else:
            self._source = None
    
    ### Properties ###
    def get_status(self):
        return self._status[0]
    def set_status(self, status):
        if isinstance(status, basestring):
            status = (status, '')
        self._status = status
    status = property(get_status, set_status)
    
    def get_extra(self):
        return self._extra
    def set_extra(self, extra):
        self._extra = extra
    extra = property(get_extra, set_extra)
    
    @property
    def slug(self):
        slug = os.path.basename( os.path.abspath(self.properties.get('path', '')) )
        if slug:
            return slug
        else:
            return self.properties.get('path')
    
    @property
    def priority(self):
        if (self._service):
            return self._service.priority
        return self.properties.get('priority', 0)
    
    @property
    def path(self):
        return self.properties['path']
    
    ### Methods ###
    def deploy(self):
        if self._service:
            return
        self._threads.append( eventlet.spawn(self._deploy) )
        self.status = 'deploying'
    
    def _deploy(self):
        if self.disabled:
            self.status = 'disabled'
            return
        
        self.status = 'updating'
        if self._source is not None:    
            if not self._source.update(self.path):
                self.status = 'mia'
                return
        
        self.status = "deploying"
        
        try:
            config = {}
            config.update(self.load_config())
            config.update(self.properties)
            config['_manager'] = self._manager
            config['slug'] = self.slug
            
            if not config.get('type'):
                self.status = "mia"
                self._manager._log.error("Cannot find service:", self.path)
                return
            
            self._service = Resource.create(config)
        except Exception, e:
            self._manager._log.exception(e)
        
        if self._service.disabled:
            self.status = 'disabled'
        else:
            self._service.start()
        
        self._threads.append( eventlet.spawn(self._check_status_loop) )
        if (self._service.health):
            #print "Health Checker engaged [timeout: %r, interval: %r]" % (self._service.health.get('interval', 30), self._service.health.get('timeout', 10))
            self._threads.append( eventlet.spawn(self._check_health_loop, self._service.health.get('interval', 30)) )
        self._threads.remove( eventlet.getcurrent() )
        
        self._manager.services.sort()
    
    def match_path(self, path):
        if not self._service:
            raise RuntimeError("Token not deployed.")
        return self._service.match_path(path)
    
    def match_site(self, hostname):
        if not self._service:
            raise RuntimeError("Token not deployed.")
        return self._service.match_site(hostname)
    
    def check_source(self):
        if self._source:
            return self._source.check(self.path)
        return True
        
    def is_valid(self):
        config = self.load_config()
        if config.get('type', None):
            return True
        return False
            
    def load_config(self):
        path = os.path.join( self.properties.get('path'), 'deploy.json' )
        if os.path.exists(path):
            try:
                self._config_file = MutableFile(path)
                self._config = fix_unicode_keys( json.load(self._config_file) )
                if not self.type:
                    self.type = self._config.get('type', None)
            except Exception, e:
                self._manager._log.exception(e)
                self._config_file = None
                self._config = {}
            return self._config
        else:
            self._config_file = None
            self._config = {}
            return self._config
    
    def withdraw(self):
        self.status = "withdrawing"
        self._withdraw()
        self.status = 'disabled'
    
    def _withdraw(self):
        if self._threads:
            for g in self._threads:
                if g is not eventlet.getcurrent():
                    self._threads.remove(g)
                    eventlet.kill(g)
        
        if self._service:
            self._service.stop()
            self._service = None
        
    def redeploy(self):
        self.status = 'redeploying'
        self._withdraw()
        self.deploy()
    
    def _check_status_loop(self, interval=0.5):
        while True:
            try:
                if self._config_file and self._config_file.is_stale():
                    self._manager._log.info("reloading service: %s", self.properties.get('path'))
                    return self.redeploy()
                self.status = self._service.check_status()
            except Exception, e:
                self._manager._log.exception(e)
            eventlet.sleep(interval)
    
    def _check_health_loop(self, interval=30):
        while True:
            eventlet.sleep(interval)
            try:
                self._service.check_health()
            except Exception, e:
                self._manager._log.exception(e)
    
    def info(self):
        if (self._service):
            info = self._service.simple()
        else:
            info = self.simple()
        info['status'], info['statusText'] = self._status
        info['statusDescription'] = TOKEN_STATES.get(self.status, '')
        info['name'] = info.get('name', os.path.basename(info['path']))
        return info
    
    def remove(self):
        import shutil
        
        self._withdraw()
        shutil.rmtree(self.path, True)
    
    def simple(self):
        return self.properties.copy()
    
    def __call__(self, environ, start_response):
        return self._service(environ, start_response)
        