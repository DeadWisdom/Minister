import os, sys, signal, errno, time, logging

from eventlet.green import socket

try:
    from minister.resource import Resource
    from minister.proxy import Proxy
    from minister.util import json, fix_unicode_keys
except ImportError:
    print os.environ
    raise RuntimeError("Unable to find minister in our environment.")

class Service(Resource):
    ### Properties #######################
    address = ('', 0)
    args = None
    before_deploy = []
    disabled = False
    environ = {}
    executable = sys.executable
    layout = None
    manager = None
    name = 'Unnamed Service'
    num_processes = 2
    path = None
    requires = ['minister', 'eventlet']
    site = None
    url = None
    type = 'service'
    health = None
    
    log_level = "INFO"
    log_count = 4
    log_max_bytes = 2**24       # 16Mb
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_echo = False
    
    _failed = False

    ### Class Methods #####################
    @classmethod
    def rebuild(cls, dct=None):
        if dct is None:
            dct = fix_unicode_keys( json.loads(os.environ['SERVICE_JSON']) )
        
        instance = Resource.create(dct)
        
        if '_socket' in dct:
            fd = dct.pop('_socket')
            instance._socket = socket.fromfd( fd, socket.AF_INET, socket.SOCK_STREAM )
        
        return instance
    
    ### Instance Methods ###################
    def init(self):
        if not getattr(self, '_socket', None):
        
            self._socket = socket.socket()
            self._socket.bind(tuple(self.address))
            self._socket.listen(500)
        
            self.address = self._socket.getsockname()
            self._proxy = Proxy(address=self.address)
            self._processes = []
            
        self.layout = Resource.create(self.layout)
    
    def simple(self):
        """
        Return the simplified properties of this instance so that it can be JSONed.
        """
        dct = dict((k, v) for k, v in self.__dict__.items() if not k.startswith('_'))
        if getattr(self, '_socket', None):
            dct['_socket'] = self._socket.fileno()
        if getattr(self, 'layout', None):
            dct['layout'] = self.layout.simple()
        return dct
    
    def get_environ(self):
        """
        This dictionary is added to our environment for a child process.
        """
        environ = os.environ.copy()
        environ.update(self.environ)
        environ.update({
            'SERVICE_URL': str(self.url),
            'SERVICE_PATH': str(self.path),
            'SERVICE_JSON': json.dumps(self.simple()),
        })
        
        # Add our socket.
        if hasattr(self, '_socket'):
            environ['SERVICE_SOCKET'] = str(self._socket.fileno())
        
        # Place our cwd in the Python Path:
        pypath = environ.get('PYTHONPATH')
        if pypath:
            environ['PYTHONPATH'] = "%s:%s" % (os.path.abspath(os.curdir), pypath)
        else:
            environ['PYTHONPATH'] = os.path.abspath(os.curdir)
        
        return environ
    
    def __call__(self, environ, start_response):
        """
        For use as a wsgi app, will pipe to our proxy.
        """
        if self.layout:
            environ['SERVICE_PATH'] = self.path
            response = self.layout(environ, start_response)
            del environ['SERVICE_PATH']
            if response:
                return response
        
        return self._proxy(environ, start_response)
    
    def start(self):
        self.stop()
            
        if self.before_deploy:
            self.shell(self.before_deploy)
        
        for i in xrange(self.num_processes):
            try:
                process = Process(self.path, self.executable, self.args, self.get_environ())
                self._processes.append( process )
                process.run()
            except:
                logging.getLogger('minister').exception("process startup failed")
    
    def shell(self, cmd):
        from minister.util import system
        if isinstance(cmd, basestring):
            cmd = {'command': cmd}
        if isinstance(cmd, list):
            return "\n".join(self.shell(c[1]) for c in cmd)
        if 'path' in cmd:
            path = os.path.join(self.path, cmd['path'])
        else:
            path = self.path
        result, content = system(path, cmd['command'], cmd.get('args', []))
        if result != 0:
            raise RuntimeError("Command failed:", cmd)
        return content
    
    def stop(self):
        if hasattr(self, '_processes'):
            for process in self._processes:
                process.kill()
        self._processes = []
    
    def check_status(self):
        if self.disabled:
            return "disabled"
            
        if self._failed:
            return "failed"
            
        active = 0
        failed = True
        for process in self._processes:
            done, status = process.check()
            if not done:
                failed = False
                active += 1
            elif process.is_failure():
                process.kill()
                self._processes.remove(process)
            else:
                failed = False
                process.kill()
                process.run()
        
        total = self.num_processes
        plural = 'es'
        if total == 1:
            plural = ''
        
        if failed:
            logging.getLogger('minister').error("service failed: %s", self.path)
            self._failed = True
            return 'failed', '0 of %d process%s' % (total, plural)
        elif active == total:
            return 'active', '%d of %d process%s' % (active, total, plural)
        elif active < total:
            return 'struggling', '%d of %d process%s' % (active, total, plural)

    def check_health(self):
        return True
        
        ## This isn't working yet.
        from eventlet.green import httplib
        try:
            timeout = self.health.get('timeout', 10)
            conn = httplib.HTTPConnection(self.address[0], self.address[1], True, timeout)
            conn.request("get", self.health.get('url', ''))
            status = conn.getresponse().status
        except Exception, e:
            status = None
        if status != 200:
            for p in self._processes:
                p.kill()
                p.run()

class Process(object):
    def __init__(self, path=None, executable=sys.executable, args=[], environ={}):
        self.pid = None
        self.path = os.path.abspath( path )
        self.executable = executable
        self.args = args
        self.environ = environ
        self.events = []
    
    def run(self):
        self.event('run')
        self.pid = os.fork()
        if not self.pid:
            self._exec()
    
    def event(self, name):
        self.events.append((name, time.clock()))
        self.events = self.events[:20]
    
    def check(self):
        try:
            return os.waitpid(self.pid, os.WNOHANG)
        except OSError, e:
            if e.errno == 10:
                return True, None
        return 0, None
    
    def is_failure(self, leeway=30):
        runs = filter(lambda x: x[0] == 'run', self.events)
        if len(runs) < 3:
            return False
        else:
            #It's a failure if the third to last run was less than <leeway> seconds ago.
            return (time.clock() - runs[-3][1]) < leeway
    
    def kill(self):
        if self.pid:
            self.event('kill')
            try:
                os.kill(self.pid, signal.SIGHUP)
                os.waitpid(self.pid, 0)
                self.pid = None
            except OSError:
                pass
    
    def _exec(self):
        try:
            os.chdir(self.path)
            args = [self.executable] + list(self.args)
            os.execvpe(self.executable, args, self.environ)
        except OSError, e:
            logging.getLogger('minister').error("%s - %s", " ".join(args), str(e))
            os._exit(0)
        except Exception, e:
            logging.getLogger('minister').exception("process startup failed")
            os._exit(0)


