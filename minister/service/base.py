import os, sys, logging

from eventlet.green import socket, subprocess

try:
    import minister
except ImportError, e:
    print sys.path
    print os.environ
    raise RuntimeError( "Unable to find minister in our environment." )

from minister.process import Process
from minister.resource import Resource
from minister.proxy import Proxy
from minister.util import shell, json, fix_unicode_keys, get_logger, path_insert

class Service(Resource):
    """
    Service base, all services should be subclasses of this.
    """
    
    type = 'service'
    
    ### Properties #######################
    before_deploy = []
    name = 'Unnamed Service'
    path = None
    resources = None
    
    _manager = None
    _logger = logging.getLogger("minister")
    
    ### Instance Methods ###################
    def __init__(self, **kw):
        super(Service, self).__init__(**kw)
        self.resources = Resource.create(self.resources)
    
    def __call__(self, environ, start_response):
        """For use as a wsgi app, will pipe to our proxy."""
        if self.resources:
            response = self.resources(environ, start_response)
            if response:
                return response
    
    def start(self):
        if self.before_deploy:
            cmds = self.before_deploy
            if isinstance(cmds, basestring):
                cmds = [cmds]
            
            for cmd in cmds:
                out, err = shell(self.path, cmd)
                if err:
                    self._logger.error('> %s\n%s', cmd, err)
                    self.stop()
                    return False
                elif out:
                    self._logger.info('> %s\n%s', cmd, out)
        
        self.disabled = False
        return True
    
    def stop(self):
        self.disabled = True
        
    def restart(self):
        self.stop()
        return self.start()
    
    def get_health(self):
        if self.disabled:
            return False, "disabled"

        return True, "active"


class ProxyService(Service):
    """
    A proxy service will requests to some address.
    """
    
    type = "proxy:service"
    
    ### Properties #######################
    address = ('', 0)
    
    ### Methods ##########################
    def __init__(self, **kw):
        super(ProxyService, self).__init__(**kw)
        self._proxy = Resource.create({'type': 'proxy', 'address': self.address})
    
    def __call__(self, environ, start_response):
        """
        For use as a wsgi app, will pipe to our proxy.
        """
        response = super(ProxyService, self).__call__(environ, start_response)
        if response is not None:
            return response
        return self._proxy(environ, start_response)


class ProcessService(Service):
    """
    A proxy service will run a process when it is started.
    """
    type = "process:service"
    
    ### Properties #######################    
    args = []
    environ = {}
    executable = sys.executable
    count = 1
    
    ### Methods ##########################
    def __init__(self, **kw):
        super(ProcessService, self).__init__(**kw)
        self._processes = []
        
    def start(self):
        environ = self.get_environ()
        for i in xrange(self.count):
            process = Process(self.path, self.executable, self.args, environ, self._logger)
            self._processes.append( process )
            process.run()
        
        return super(ProcessService, self).start()
        
    def stop(self):
        for process in self._processes:
            process.kill()
        self._processes = []
        
        super(ProcessService, self).stop()
    
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
            'SERVICE_MANAGER_PATH': self._manager.path,
        })
        
        # Place our path in the Path:
        path_insert(environ, 'PATH', os.path.abspath(os.curdir))
        path_insert(environ, 'PATH', os.path.abspath(self.path))
        
        environ['OLDPWD'] = environ['PWD']
        environ['PWD'] = os.path.abspath(self.path) 
        
        return environ
    
    def get_health(self, strict=False):
        """
        This will get the health of the processes, any dead processes will be 
        restarted until they are marked failed.  If strict is true,
        no processes will be restarted; they have to be running or they fail.
        """
        if self.disabled:
            return False, "disabled"
            
        active = 0
        failed = True
        for process in self._processes:
            if process.check():
                failed = False
                active += 1
            elif process.is_failure() or strict:
                process.kill()
                self._processes.remove(process)
            else:
                failed = False
                process.kill()
                process.run()
        
        total = self.count
        plural = 'es'
        if total == 1:
            plural = ''
        
        if failed:
            self._logger.error("service failed: %s", self.path)
            return False, '0 of %d process%s' % (total, plural)
        elif active == total:
            return True, '%d of %d process%s' % (active, total, plural)
        elif active < total:
            return True, '%d of %d process%s' % (active, total, plural)

class ProcessProxyService(ProxyService, ProcessService):
    """
    Combines a proxy and process service.  Also, this will bind on a socket 
    before creating the processes, so that each process can use that socket.
    can 
    """
    
    type = "processproxy:service"
    socket = None
    
    def __init__(self, **kw):
        if not self.socket:
            self.socket = socket.socket()
            self.socket.bind( tuple(kw.get('address', self.address)) )
            self.socket.listen(500)
        elif isinstance(self.socket, int):
            self.socket = socket.fromfd( self.socket, socket.AF_INET, socket.SOCK_STREAM )
        
        kw['address'] = self.socket.getsockname()
        super(ProcessProxyService, self).__init__(**kw)
    
    def get_environ(self):
        """
        Adds our socket.
        """
        environ = super(ProcessProxyService, self).get_environ()
        environ['SERVICE_SOCKET'] = str(self.socket.fileno())
        return environ
    
    def simple(self):
        dct = super(ProcessProxyService, self).simple()
        dct['socket'] = self.socket.fileno()
        return dct
        

class PythonService(ProcessProxyService):
    type = "python:service"
    
    ### Properties #######################
    virtualenv = "env"
    requires = ['minister', 'eventlet']
    
    ### Methods ##########################
    def start(self):
        if self.virtualenv:
            cmd = 'pip install -E %s %s' % (self.virtualenv, " ".join(self.requires))
            out, err = shell(self.path, cmd)
        
            if err:
                self._logger.error('> %s\n%s', cmd, err)
                self.stop()
                return False
            elif out:
                self._logger.info('> %s\n%s', cmd, out)
        
        return super(PythonService, self).start()
    
    def get_environ(self):
        environ = super(PythonService, self).get_environ()
        
        ### Put our virtual env in the environ
        if self.virtualenv:
            path = os.path.abspath(os.path.join(self.path, self.virtualenv))
            environ['VIRTUAL_ENV'] = path
            path_insert(environ, 'PATH', os.path.join(path, 'bin'))
        
        path_insert(environ, 'PYTHONPATH', os.path.abspath(self.path))
        path_insert(environ, 'PYTHONPATH', os.path.abspath(os.curdir))
        
        return environ
    
    @classmethod
    def setup_backend(cls, dct=None):
        """
        This is called by a backend (child) python process to setup the
        environment and create a simple object representing the service
        settings gleamed from the os.environ key SERVICE_JSON.
        """
        if dct is None:
            dct = fix_unicode_keys( json.loads(os.environ['SERVICE_JSON']) )
        
        dct['socket'] = socket.fromfd( dct['socket'], socket.AF_INET, socket.SOCK_STREAM )
        
        return dct

#class Service(Resource):
#    ### Properties #######################
#    address = ('', 0)
#    port_range = (10000, 20000)
#    args = None
#    before_deploy = []
#    disabled = False
#    environ = {}
#    executable = sys.executable
#    layout = None
#    name = 'Unnamed Service'
#    slug = None
#    count = 2
#    path = None
#    requires = ['minister', 'eventlet']
#    site = None
#    url = ''
#    type = 'service'
#    health = None
#    
#    log_level = "INFO"
#    log_count = 4
#    log_max_bytes = 2**24       # 16Mb
#    log_format = "%(asctime)s - %(levelname)s - %(message)s"
#    log_echo = False
#    
#    _failed = False
#    _manager = None
#    
#    ### Class Properties ##################]
#    _used_addresses = set()
#
#    ### Class Methods #####################
#    @classmethod
#    def setup_backend(cls, dct=None):
#        """
#        This is called by a backend (child) python process to setup the
#        environment and create a simple object representing the service
#        settings gleamed from the os.environ key SERVICE_JSON.
#        """
#        if dct is None:
#            dct = fix_unicode_keys( json.loads(os.environ['SERVICE_JSON']) )
#        
#        if '_socket' in dct:
#            dct['socket'] = socket.fromfd( dct['_socket'], socket.AF_INET, socket.SOCK_STREAM )
#        
#        if 'SERVICE_MANAGER_PATH' in os.environ:
#            dct['logger'] = get_logger(path=os.environ['SERVICE_MANAGER_PATH'],
#                                       name=dct['slug'],
#                                       level=dct.get('log_level', cls.log_level),
#                                       max_bytes=dct.get('log_max_bytes', cls.log_max_bytes),
#                                       count=dct.get('log_count', cls.log_count),
#                                       format=dct.get('log_format', cls.log_format),
#                                       echo=dct.get('log_echo', cls.log_echo))
#            dct['log'] = FileLikeLogger(dct['slug'])
#        
#        sys.path.insert(0, dct['path'])
#        
#        return dct
#    
#    ### Instance Methods ###################
#    def __init__(self, **kw):
#        super(Service, self).__init__(**kw)
#        if self.slug.startswith('@'):
#            self._log = logging.getLogger('minister')
#        else:
#            self._log = get_logger(path=self._manager.path,
#                                   name=self.slug,
#                                   level=self.log_level,
#                                   max_bytes=self.log_max_bytes,
#                                   count=self.log_count,
#                                   format=self.log_format,
#                                   echo=self.log_echo)
#    
#    def init(self):
#        self._socket = socket.socket()
#        self._socket.bind(tuple(self.address))
#        self._socket.listen(500)
#    
#        self.address = self._socket.getsockname()
#        self._proxy = Proxy(address=self.address)
#        self._processes = []
#            
#        self.layout = Resource.create(self.layout)
#    
#    def simple(self):
#        """
#        Return the simplified properties of this instance so that it can be JSONed.
#        """
#        dct = dict((k, v) for k, v in self.__dict__.items() if not k.startswith('_'))
#        if getattr(self, '_socket', None):
#            dct['_socket'] = self._socket.fileno()
#        if getattr(self, 'layout', None):
#            dct['layout'] = self.layout.simple()
#        return dct
#    
#    def get_environ(self):
#        """
#        This dictionary is added to our environment for a child process.
#        """
#        environ = os.environ.copy()
#        environ.update(self.environ)
#        environ.update({
#            'SERVICE_URL': str(self.url),
#            'SERVICE_PATH': str(self.path),
#            'SERVICE_JSON': json.dumps(self.simple()),
#            'SERVICE_MANAGER_PATH': self._manager.path,
#        })
#        
#        # Add our socket.
#        if hasattr(self, '_socket'):
#            environ['SERVICE_SOCKET'] = str(self._socket.fileno())
#        
#        # Place our cwd in the Python Path:
#        pypath = environ.get('PYTHONPATH')
#        if pypath:
#            environ['PYTHONPATH'] = "%s:%s" % (os.path.abspath(os.curdir), pypath)
#        else:
#            environ['PYTHONPATH'] = os.path.abspath(os.curdir)
#        
#        return environ
#    
#    def __call__(self, environ, start_response):
#        """
#        For use as a wsgi app, will pipe to our proxy.
#        """
#        if self.layout:
#            environ['SERVICE_PATH'] = self.path
#            response = self.layout(environ, start_response)
#            del environ['SERVICE_PATH']
#            if response:
#                return response
#        
#        return self._proxy(environ, start_response)
#    
#    def start(self):
#        self.stop()
#            
#        if self.before_deploy:
#            if isinstance(self.before_deploy, basestring):
#                self.shell(self.before_deploy)
#            else:
#                for cmd in self.before_deploy:
#                    self.shell(cmd)
#        
#        for i in xrange(self.count):
#            process = Process(self.path, self.executable, self.args, self.get_environ(), self._log)
#            self._processes.append( process )
#            process.run()
#    
#    def shell(self, cmd):
#        args = shlex.split(str(cmd))
#        try:
#            popen = subprocess.Popen(list(args), cwd=self.path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#            out, err = popen.communicate()
#        except OSError, e:
#            err = str(e)
#            out = None
#        
#        if err:
#            self._log.error('> %s\n%s', cmd, '\n...  '.join([line for line in err.split('\n')]))
#            
#        if out:
#            self._log.info('> %s\n%s', cmd, '\n...  '.join([line for line in out.split('\n')]))
#        
#        return out or err
#    
#    def stop(self):
#        if hasattr(self, '_processes'):
#            for process in self._processes:
#                process.kill()
#        self._processes = []
#    
#    def check_status(self):
#        if self.disabled:
#            return "disabled"
#            
#        if self._failed:
#            return "failed"
#            
#        active = 0
#        failed = True
#        for process in self._processes:
#            if process.check():
#                failed = False
#                active += 1
#            elif process.is_failure():
#                process.kill()
#                self._processes.remove(process)
#            else:
#                failed = False
#                process.kill()
#                process.run()
#        
#        total = self.count
#        plural = 'es'
#        if total == 1:
#            plural = ''
#        
#        if failed:
#            logging.getLogger('minister').error("service failed: %s", self.path)
#            self._failed = True
#            return 'failed', '0 of %d process%s' % (total, plural)
#        elif active == total:
#            return 'active', '%d of %d process%s' % (active, total, plural)
#        elif active < total:
#            return 'struggling', '%d of %d process%s' % (active, total, plural)
#
#    def check_health(self):
#        return True
#        
#        ## This isn't working yet.
#        from eventlet.green import httplib
#        try:
#            timeout = self.health.get('timeout', 10)
#            conn = httplib.HTTPConnection(self.address[0], self.address[1], True, timeout)
#            conn.request("get", self.health.get('url', ''))
#            status = conn.getresponse().status
#        except Exception, e:
#            status = None
#        if status != 200:
#            for p in self._processes:
#                p.kill()
#                p.run()
#                
#    def find_port(self):
#        host = self.address[0]
#        for port in range(*self.port_range):
#            if (host, port) in self._used_addresses:
#                continue
#            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#            try:
#                s.bind((host, port))
#            except socket.error, e:
#                continue
#            else:
#                self._used_addresses.add((host, port))
#                s.close()
#                return host, port