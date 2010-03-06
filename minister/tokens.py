from eventlet import api

try:
    import json
except ImportError:
    import simplejson as json

import sys, os
from uuid import uuid4
from service import Service
from resource import Resource
from source import Source
from util import MutableFile, fix_unicode_keys, print_tb

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
        self._thread = None
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
    def path(self):
        return self.properties['path']
    
    ### Methods ###
    def deploy(self):
        if self._service:
            return
        self._thread = api.spawn(self._deploy)
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
            
            self._service = Resource.create(config)
            self._service._manager = self._manager
        except Exception, e:
            print_tb(e)
            raise e
        
        if self._service.disabled:
            self.status = 'disabled'
        else:
            print "Start:", self.path
            self._service.start()
        
        self.monitor()
    
    def match_path(self, path):
        if not self._service:
            raise RuntimeError("Token not deployed.")
        if self._service.disabled:
            return False
        url = self._service.url
        if url is None:
            return path
        if url is not None and path.startswith(url):
            return path[len(url):]
    
    def match_sites(self, hostname):
        if not self._service:
            raise RuntimeError("Token not deployed.")
        if self._service.disabled:
            return False
        if self._service.sites is None:
            return True
        if hostname in self._service.sites:
            return True
    
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
                print e
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
        if self._thread and self._thread is not api.getcurrent():
            api.kill(self._thread)
            self._thread = None
        
        if self._service:
            self._service.stop()
            self._service = None
        
    def redeploy(self):
        self.status = 'redeploying'
        self._withdraw()
        self.deploy()
    
    def monitor(self, interval=0.5):
        while True:
            if self._config_file and self._config_file.is_stale():
                return self.redeploy()
            self.status = self._service.check_status()
            api.sleep(interval)
    
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
        