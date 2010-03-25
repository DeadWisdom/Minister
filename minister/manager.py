import os, sys, atexit

import eventlet
from eventlet import wsgi
from eventlet.green import socket

from http import Http404, Http500
from resource import Resource
from tokens import ServiceToken
from service import Service
from util import json, fix_unicode_keys, get_logger, FileLikeLogger
from debug import HttpDebug500, HttpDebug404

class Manager(Resource):
    type = 'manager'
    path = None
    layout = None
    services = None
    debug = False
    
    log_level = "DEBUG"
    log_count = 4
    log_max_bytes = 2**25       # 32Mb
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_echo = False
    
    def init(self):
        self.path = os.path.abspath(self.path)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        
        self._log = get_logger(self.path,
                               "minister",
                               level=self.log_level,
                               max_bytes=self.log_max_bytes,
                               count=self.log_count,
                               format=self.log_format,
                               echo=self.log_echo)
                               
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
            eventlet.kill( self._threads.pop() )
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
            self._log.info("loading service: %s", token.properties.get('path'))
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
            
            if (address[0] == ''):
                address = 'localhost', address[1]
            
            self.address = address
            
            print "Manager servering on http://%s:%s" % address
            self._log.info("manager serving on http://%s:%s", *address)
            wsgi.server(self._socket, self, log=FileLikeLogger('minister'))
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
                eventlet.sleep(interval)
                method()
        self._threads.append( eventlet.spawn(loop) )
    
    def update(self):
        for token in self._tokens.values():
            if token.status in ("active", "failed", "disabled", "mia"):
                try:
                    if token.check_source():
                        self._log.info("reloading service: %s", token.properties.get('path'))
                        token.redeploy()
                except Exception, e:
                    self._log.exception("error updating service: %s", e)
                
    def scan(self):
        service_path = os.path.join(self.path, 'services')
        new = []
        for filename in os.listdir( service_path ):
            try:
                path = os.path.join(service_path, filename)
                if os.path.isdir(path) and path not in self._tokens:
                    t = ServiceToken({'path': os.path.abspath(path)})
                    if t.is_valid():
                        new.append(t)
                        self._tokens[t.path] = t
                        self.services.resources.append(t)
                        t._manager = self
                        t.deploy()
            except Exception, e:
                self._log.exception("error scanning file (%s): %s", filename, e)
                
        if new:
            self.save()
            self._log.info("new services found: \n%s" % "  \n".join([t.properties.get('path') for t in new]))

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
                        
    parser.add_option("-v", "--verbose", 
                        action="store_true", dest="verbose",
                        help="Output logging info to stdout.", 
                        default=False)
                        
    parser.add_option("-d", "--debug", 
                        action="store_true", dest="debug",
                        help="Run in debug mode.", 
                        default=False)
    
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
    if options.verbose:
        config['log_echo'] = "DEBUG"
    else:
        config['log_echo'] = "WARNING"
    
    if options.debug:
        config['debug'] = True
    
    manager = Manager(**config)
    atexit.register(manager.close)
    manager.serve(address)
