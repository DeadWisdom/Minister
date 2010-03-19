import os, sys, atexit

from eventlet import wsgi, api
from eventlet.green import socket

from http import Http404, Http500
from resource import Resource
from tokens import ServiceToken
from service import Service
from util import json, fix_unicode_keys, print_tb
from debug import HttpDebug500, HttpDebug404

class Manager(Resource):
    type = 'manager'
    path = None
    layout = None
    services = None
    debug = True
    
    def init(self):
        self.path = os.path.abspath(self.path)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        
        tokens = [ServiceToken(s) for s in self.services]
        for t in tokens:
            t._manager = self
        self.services = Resource.create( tokens )
        self.layout = Resource.create( self.layout or [] )
        
        self._tokens = dict((t.path, t) for t in tokens)
        self._threads = []
        self._socket = None
    
    def save(self):
        file = open(os.path.join(self.path, 'config.json'), 'w')
        json.dump(self.simple(), file)
    
    def close(self):
        while self._threads:
            api.kill( self._threads.pop() )
        if self._socket:
            try:
                self._socket.shutdown()
            except:
                pass
        for token in self.services.resources:
            try:
                token.withdraw()
            except:
                pass
    
    def serve(self, address=('', 8000), debug=False):
        if self._socket:
            return
        
        for token in self._tokens.values():
            print "loading service -", token.properties.get('path')
            token.deploy()
            
        service_path = os.path.join(self.path, 'services')
        if not os.path.exists(service_path):
            os.makedirs(service_path)
        
        self.periodically(self.scan, 1)
        self.periodically(self.update, 60 * 30)
        
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(address)
            self._socket.listen(500)
            
            wsgi.server(self._socket, self)#, log=open(os.devnull, 'w'))
        finally:
            self.close()
        
    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = environ['PATH_INFO'][1:]
        
        try:
            response = self.layout(environ, start_response)
            if response is not None:
                return response
            
            response = self.services(environ, start_response)
            if response is not None:
                return response
        except:
            exc = sys.exc_info()
            if self.debug:
                return HttpDebug500(environ, start_response, exc)
            else:
                return Http500(environ, start_response)
        
        if self.debug:
            return HttpDebug404(environ, start_response, self)
        else:
            return Http404(environ, start_response)
    
    def periodically(self, method, interval=1):
        def loop():
            while True:
                api.sleep(interval)
                try:
                    method()
                except Exception, e:
                    from util import print_tb
                    print_tb(e)
        self._threads.append( api.spawn(loop) )
    
    def update(self):
        for token in self._tokens.values():
            if token.status in ("active", "failed", "disabled", "mia"):
                if token.check_source():
                    token.redeploy()
                
    def scan(self):
        service_path = os.path.join(self.path, 'services')
        new = []
        for filename in os.listdir( service_path ):
            path = os.path.join(service_path, filename)
            if os.path.isdir(path) and path not in self._tokens:
                t = ServiceToken({'path': os.path.abspath(path)})
                if t.is_valid():
                    new.append(t)
                    self._tokens[t.path] = t
                    self.services.resources.append(t)
                    t._manager = self
                    t.deploy()
        if new:
            self.save()
            print "new services found:"
            for t in new:
                print " ", t.properties.get('path')

def run():
    from optparse import OptionParser

    usage = "usage: %prog [port or ip:port]"
    parser = OptionParser(usage=usage)
    
    parser.add_option("-p", "--path", 
                        dest="path", 
                        help="Use PATH as the home directory, defaults to /var/minister if run as root, or ~/.minister if not", 
                        metavar="PATH", 
                        default=None)
                        
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

    if options.path is None:
        options.path = os.path.expanduser("~/.minister")

    try:
        file = open(os.path.join(options.path, 'config.json'))
        config = fix_unicode_keys( json.load( file ) )
    except IOError, e:
        config = {
            'services': [{'type': 'admin', 'path': '@admin'}],
        }
    
    config['path'] = options.path
    
    manager = Manager(**config)
    atexit.register(manager.close)
    manager.serve(address)
