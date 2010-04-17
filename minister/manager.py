import os, sys, atexit

import eventlet
from eventlet import wsgi
from eventlet.green import socket

import daemon
from http import NotFound, InternalServerError
from debug import DebugNotFound, DebugInternalServerError
from resource import Resource
from tokens import ServiceToken
from service import Service
from util import json, fix_unicode_keys, FileLikeLogger
from logger import get_logger, make_logger

class Manager(Resource):
    type = 'manager'
    path = None
    resources = []
    services = []
    debug = False
    address = None
    log = dict(
        level = "DEBUG",
        count = 4,
        bytes = 2**25,       # 32Mb
        format = "%(asctime)s - %(levelname)s - %(message)s",
        echo = False,
        path = None,
        name = 'minister'
    )
    
    def init(self):
        self.path = os.path.abspath(self.path)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
            
        if isinstance(self.log, basestring):
            self.log = get_logger(self.log)
        elif isinstance(self.log, dict):
            log, self.log = self.log, {}
            self.log.update(self.__class__.log)
            self.log.update(log)
            if self.log['path'] is None:
                self.log['path'] = os.path.join(self.path, 'logs', 'minister.log')
            self.log = make_logger(**self.log)
        
        self._threads = []
        self._socket = None
        
        self._token_map = {}
        self._paths = set()
        
        self.services, services = [], self.services
        for s in services:
            self.add_service(s['path'], s)
            
        self.resources = Resource.create(self.resources)
    
    def simple(self):
        log = self.log
        del self.log
        result = super(Manager, self).simple()
        self.log = log
        return result
    
    def save(self):
        file = open(os.path.join(self.path, 'config.json'), 'w')
        try:
            json.dump(self.simple(), file, indent=4)
        finally:
            file.close()
    
    def close(self):
        while self._threads:
            eventlet.kill( self._threads.pop() )
        self._socket = None
        for service in self.services:
            try:
                service.withdraw()
            except:
                pass
    
    @classmethod
    def listen(cls, address):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(address)
        sock.listen(500)
        return sock
    
    def serve(self, where=('', 8000), debug=False):
        if self._socket:
            return
        
        for service in self.services:
            self.log.info("loading service: %s", service.path)
            service.deploy()
            
        service_path = os.path.join(self.path, 'services')
        if not os.path.exists(service_path):
            os.makedirs(service_path)
        
        self.periodically(self.scan, 1)
        self.periodically(self.update, 60 * 30)
        
        try:
            if isinstance(where, socket.socket):
                self._socket = where
            else:
                self._socket = self.listen(where)
            
            self.address = self._socket.getsockname()
            
            print "Manager servering on http://%s:%s" % self.address
            self.log.info("manager serving on http://%s:%s", *self.address)
            wsgi.server(self._socket, self, log=FileLikeLogger('minister'))
        except Exception, e:
            raise e
        finally:
            self.close()
        
    def __call__(self, environ, start_response):
        environ['ORIG_PATH_INFO'] = environ['PATH_INFO']
        environ['SCRIPT_NAME'] = '/'
        environ['PATH_INFO'] = environ['PATH_INFO'][1:]
        
        try:
            response = self.resources(environ, start_response)
            if response is not None:
                return response
            
            requested_path = environ.get('PATH_INFO', '')
            hostname, _, _ = environ.get('HTTP_HOST').partition(":")
            for service in self.services:
                if service.disabled or not service.service:
                    continue
                if not service.match_site(hostname):
                    continue
                delta = service.match_path(requested_path)
                if delta is not None:
                    environ['SCRIPT_NAME'] = environ['SCRIPT_NAME'] + requested_path[:len(requested_path)-len(delta)]
                    environ['PATH_INFO'] = delta
                    return service(environ, start_response)
        except Exception, e:
            if self.debug:
                return DebugInternalServerError(sys.exc_info())(environ, start_response)
            else:
                return InternalServerError()(environ, start_response)
        
        if self.debug:
            return DebugNotFound(self)(environ, start_response)
        else:
            return NotFound()(environ, start_response)
    
    def periodically(self, method, interval=1):
        def loop():
            while True:
                method()
                eventlet.sleep(interval)
        self._threads.append( eventlet.spawn(loop) )
    
    def update(self):
        for service in self.services:
            if service.status in ("active", "failed", "disabled", "mia"):
                try:
                    if service.check_source():
                        self.log.info("reloading service: %s", service.path)
                        service.redeploy()
                except Exception, e:
                    self.log.exception("error updating service: %s", e)
    
    def get_service(self, k):
        return self._token_map[k]
    
    def add_service(self, path, override=None):
        t = ServiceToken(self, path, override)
        self._token_map[t.slug] = t
        self._paths.add(path)
        self.services.append(t)
        return t
    
    def has_service(self, path):
        return path in self._paths
    
    def scan(self):
        service_path = os.path.join(self.path, 'services')
        new = []
        for filename in os.listdir( service_path ):
            path = os.path.join(service_path, filename)
            if os.path.isdir(path) and not self.has_service(path):
                s = self.add_service(path)
                new.append(s)
                if s.is_valid():
                    s.deploy()
        if new:
            self.save()
            self.log.info("new services found: \n   %s" % "\n   ".join([s.path for s in new]))

def set_process_owner(spec, group=None):
    import pwd, grp
    if ":" in spec:
        user, group = spec.split(":", 1)
    else:
        user, group = spec, group
    if group:
        os.setgid(grp.getgrnam(group).gr_gid)
    if user:
        os.setuid(pwd.getpwnam(user).pw_uid)
    return user, group

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
                        help="Run as USER (defaults to www-data if run by root)", 
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
                        
    parser.add_option('--start', 
                        dest='start', 
                        action='store_true',
                        help="Start the process as a daemon.")
                        
    parser.add_option('--stop', 
                        dest='stop', 
                        action='store_true',
                        help="Stop the daemon.")
                        
    parser.add_option('--restart', 
                        dest='restart', 
                        action='store_true',
                        help="Restart the process daemon.")
    
    we_are_root = (os.geteuid() == 0)
    
    options, args = parser.parse_args()
    if len(args) > 1:
        parser.print_usage()
        return
    
    if not args:
        if we_are_root:
            address = ('0.0.0.0', 80)
        else:
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
        if we_are_root:
            options.path = '/var/minister'
        else:
            options.path = os.path.expanduser("~/.minister")
    
    if not os.path.exists(options.path):
        sys.stderr.write("Path to minister root does not exist: %s\n" % options.path)
        sys.exit(0)

    file = None
    try:
        file = open(os.path.join(options.path, 'config.json'))
        config = fix_unicode_keys( json.load( file ) )
    except IOError, e:
        config = {
            'services': [{'type': 'admin', 'path': '@admin'}],
        }
    finally:
        if file: file.close()
    
    config['path'] = options.path
    #if options.verbose:
    #    config['log_echo'] = "DEBUG"
    #else:
    #    config['log_echo'] = "WARNING"
    
    if options.debug:
        config['debug'] = True
    
    pidfile = os.path.join(options.path, 'minister.pid')
    if options.start:
        print "Minister daemon starting..."
        daemon.start(pidfile)
    elif options.stop:
        if daemon.stop(pidfile):
            print "Minister stopped."
            sys.exit(0)
        else:
            sys.exit(1)
    elif options.restart:
        daemon.stop(pidfile)
        print "Minister stopped."
        print "Minister daemon starting..."
        daemon.start(pidfile)
        
    if we_are_root:
        address = Manager.listen(address)
        set_process_owner(options.user or "www-data", options.group)
        
    manager = Manager(**config)
    atexit.register(manager.close)
    manager.serve(address)
    
