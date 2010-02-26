import os, sys, atexit

from eventlet import wsgi, api
from eventlet.green import socket

from http import Http404
from resource import Layout, Resource
from tokens import Token
from deploy import Deployment
from util import json, fix_unicode_keys, print_tb

class Manager(object):
    def __init__(self, path=None, config=None):        
        # Place our cwd in the Python Path:
        pypath = os.environ.get('PYTHONPATH')
        if pypath:
            os.environ['PYTHONPATH'] = "%s:%s" % (os.path.abspath(os.curdir), pypath)
        else:
            os.environ['PYTHONPATH'] = os.path.abspath(os.curdir)
        
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            os.makedirs(path)
        self.path = path
        self.tokens = {}
        self.socket = None
        self.threads = []
        self.layout = None
        self.config = config
        self.load()
    
    def create_resource(self, properties):
        if properties is None:
            return None
        if isinstance(properties, Resource):
            return properties
        if isinstance(properties, list):
            instance = Layout(resources=[self.create_resource(o) for o in properties])
        else:
            type = Resource.get_class(properties.get('type'))
            if not type:
                raise RuntimeError("Unnable to find type:", type)
            if issubclass(type, Deployment):
                type = Token
            instance = type(**properties)
        instance._manager = self
        return instance
    
    def load(self):
        self.tokens = {}
        
        if self.config is None:
            try:
                file = open(os.path.join(self.path, 'config.json'))
                self.config = fix_unicode_keys( json.load( file ) )
            except IOError, e:
                self.config = {
                    'layout': [{ 'type': 'admin', 'path': '@admin' }],
                }
            for k, v in self.config.items():
                setattr(self, k, v)
        
        self.layout = self.create_resource( self.layout, tokenize=True )
        
        for t in self.layout.flatten():
            if isinstance(t, Token):
                self.tokens[t.path] = t
                t._manager = self
    
    def save(self):
        file = open(os.path.join(self.path, 'config.json'), 'w')
        json.dump(self.simple(), file)
        
    def simple(self):
        return {
            'layout': self.layout.simple()
        }
    
    def close(self):
        while self.threads:
            api.kill( self.threads.pop() )
        if self.socket:
            try:
                self.socket.shutdown()
            except:
                pass
        for token in self.tokens:
            try:
                token.withdraw()
            except:
                pass
    
    def serve(self, address=('', 8000), debug=False):
        if self.socket:
            return
        
        for token in self.tokens.values():
            print "deploying -", token.slug
            token.deploy()
            
        dep_path = os.path.join(self.path, 'deployments')
        if not os.path.exists(dep_path):
            os.makedirs(dep_path)
        
        self.monitor(self.scan, 1)
        self.monitor(self.update, 60 * 30)
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(address)
            self.socket.listen(500)
            
            wsgi.server(self.socket, self.route, log=open(os.devnull, 'w'))
        finally:
            self.close()
        
    def route(self, environ, start_response):
        environ['PATH_DELTA'] = environ['PATH_INFO'][1:]
        response = self.layout(environ, start_response)
        if response is None:
            return Http404(environ, start_response)
        return response
    
    def monitor(self, method, interval=1):
        def loop():
            while True:
                try:
                    method()
                except Exception, e:
                    from util import print_tb
                    print_tb(e)
                api.sleep(interval)
        self.threads.append( api.spawn(loop) )
    
    def update(self):
        for token in self.tokens.values():
            if token.status in ("active", "failed", "disabled", "mia"):
                if token.check_source():
                    token.redeploy()
                
    def scan(self):
        dep_path = os.path.join(self.path, 'deployments')
        new = []
        for filename in os.listdir( dep_path ):
            path = os.path.join(dep_path, filename)
            if os.path.isdir(path) and path not in self.tokens:
                t = Token(path=os.path.abspath(path))
                if t.is_valid():
                    new.append(t)
                    self.tokens[path] = t
                    self.layout.resources.append(t)
                    t._manager = self
                    t.deploy()
        if new:
            self.save()
            print "new deployments found:"
            for t in new:
                print " ", t.path

def run():
    from optparse import OptionParser

    usage = "usage: %prog [port or ip:port]"
    parser = OptionParser(usage=usage)
    
    parser.add_option("-p", "--path", 
                        dest="path", 
                        help="Use PATH as the home directory, defaults to ~/.minister", 
                        metavar="PATH", 
                        default="~/.minister")
                        
    parser.add_option("-u", "--user", 
                        dest="user", 
                        help="Run as USER", 
                        metavar="USER", 
                        default=None)
                        
    parser.add_option("-g", "--group", 
                        dest="group", 
                        help="Run in GROUP.", 
                        metavar="GROUP", 
                        default=None)
    
    options, args = parser.parse_args()
    if len(args) > 1:
        parser.print_usage()
        return
    
    if not args:
        address = ('', 8000)
    else:
        ip, _, port = args[0].partition(':')
        if ip and not port:
            port, ip = ip, ''
        try:
            address = (str(ip), int(port))
        except:
            parser.print_usage()
            return
    
    atexit.register(manager.close)
    
    manager = Manager(path=options.path)
    manager.serve(address)
