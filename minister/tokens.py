from eventlet import api

try:
    import json
except ImportError:
    import simplejson as json

import sys, os
from deploy import Deployment
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

class Token(Resource):
    type = None             # Should be the deployment Type.
    src = ""
    path = ""
    disabled = False
    layout = None
    
    ### Initialization ###
    def init(self):
        self._deployment = None
        self._thread = None
        self._changed = False
        self._status = "building"
        self._extra = ""
        self._config = None
        self._config_file = None
        type, _, src = self.src.partition(":")
        self._source = Source(type=type, src=src)
    
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
        return os.path.basename( os.path.abspath(self.path) )
    
    
    ### Methods ###
    def deploy(self):
        if self._deployment:
            return
        self._thread = api.spawn(self._deploy)
        self.status = 'deploying'
    
    def _deploy(self):
        if self.disabled:
            self.status = 'disabled'
            return
        
        self.status = 'updating'
        if not self.path.startswith('@'):
            if not self._source.update(self.path):
                self.status = 'mia'
                return
                
        self.status = "deploying"
        
        try:
            config = {}
            config.update(self.load_config())
            config.update(self.simple())
            
            self._deployment = self._manager.create_resource(config)
        except Exception, e:
            print_tb(e)
            raise e
        
        if self._deployment.disabled:
            self.status = 'disabled'
        else:
            self._deployment.start()
        
        self.monitor()
    
    def match_path(self, path):
        if not self._deployment:
            raise RuntimeError("Token not deployed.")
        if self._deployment.disabled:
            return False
        url = self._deployment.url
        if url is None:
            return path
        if url is not None and path.startswith(url):
            return path[len(url):]
    
    def match_sites(self, hostname):
        if not self._deployment:
            raise RuntimeError("Token not deployed.")
        if self._deployment.disabled:
            return False
        if self._deployment.sites is None:
            return True
        if hostname in self._deployment.sites:
            return True
    
    def check_source(self):
        return self._source.check(self.path)
        
    def is_valid(self):
        config = self.load_config()
        if config.get('type', None):
            return True
        return False
            
    def load_config(self):
        path = os.path.join( self.path, 'deploy.json' )
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
        
        if self._deployment:
            self._deployment.stop()
            self._deployment = None
        
    def redeploy(self):
        self.status = 'redeploying'
        self._withdraw()
        self.deploy()
    
    def monitor(self, interval=0.5):
        while True:
            if self._changed or (self._config_file and self._config_file.is_stale()):
                return self.redeploy()
            self.status = self._deployment.check_status()
            api.sleep(interval)
    
    def info(self):
        if (self._deployment):
            info = self._deployment.simple()
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
    
    def __call__(self, environ, start_response):
        return self._deployment(environ, start_response)
        