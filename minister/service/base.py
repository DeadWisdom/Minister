import os, sys, logging

from eventlet.green import socket, subprocess

try:
    import minister
except ImportError, e:
    raise RuntimeError( "Unable to find minister in our environment." )

from minister.process import Process
from minister.resource import Resource
from minister.proxy import Proxy
from minister.util import shell, json, fix_unicode_keys, path_insert
from minister.middleware import Middleware

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
    root = None
    middleware = None
    
    input = None
    output = None
    
    _manager = None
    
    ### Instance Methods ###################
    def __init__(self, **kw):
        super(Service, self).__init__(**kw)
        self.resources = Resource.create(self.resources)
        self.middleware = [Middleware.create(x) for x in (self.middleware or [])]
        if self.root is not None:
            self.root = os.path.abspath( os.path.join(self.path, self.root) )
            self.resources.append(Resource.create(dict(type='static', url='', root=self.root, strict=False)))
    
    def __call__(self, environ, start_response):
        """For use as a wsgi app."""
        if self.resources:
            response = self.resources(environ, start_response)
            if response:
                return response
                
    def get_app(self):
        app = self
        for m in reversed(self.middleware):
            app = m(app)
        return app
    
    def start(self):
        if self.before_deploy:
            cmds = self.before_deploy
            if isinstance(cmds, basestring):
                cmds = [cmds]
            
            for cmd in cmds:
                out, err = shell(self.path, cmd)
                if err:
                    logging.error('> %s\n%s', cmd, err)
                    self.stop()
                    return False
                elif out:
                    logging.info('> %s\n%s', cmd, out)
        
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
    port_range = (10000, 20000)
    address = ('127.0.0.1', 0)
    
    ### Methods ##########################
    def start(self):
        super(ProxyService, self).start()
        self._proxy = Resource.create({'type': 'proxy', 'address': self.address})
    
    def __call__(self, environ, start_response):
        """
        For use as a wsgi app, will pipe to our proxy.
        """
        response = super(ProxyService, self).__call__(environ, start_response)
        if response is not None:
            return response
        return self._proxy(environ, start_response)
    
    _used_addresses = set()
    def find_port(self):
        host = self.address[0]
        for port in range(*self.port_range):
            if (host, port) in self._used_addresses:
                continue
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
            except socket.error, e:
                continue
            else:
                self._used_addresses.add((host, port))
                s.close()
                return host, port


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
        logging.info("running - %s %s", self.executable, " ".join(self.args))
        for i in xrange(self.count):
            process = Process(self.path, self.executable, self.args, environ)
            self._processes.append( process )
            process.run()
        
        return super(ProcessService, self).start()
        
    def stop(self):
        for process in self._processes:
            try:
                process.kill()
            except:
                pass
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
        
        environ['OLDPWD'] = environ.get('PWD', '')
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
            logging.error("service failed: %s", self.path)
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
    requires = ['eventlet']
    
    ### Methods ##########################
    def start(self):
        if self.virtualenv:
            cmd = 'pip install -E %s %s' % (self.virtualenv, " ".join(self.requires))
            out, err = shell(self.path, cmd)
        
            if err:
                if "mysql-python" in self.requires:
                    logging.warning("mysql-python might require 'mysql_config'; 'apt-get install libmysqlclient-dev' or your package management equivalent might fix this problem.")
                logging.error('> %s\n%s', cmd, err)
                self.stop()
                return False
            elif out:
                logging.info('> %s\n%s', cmd, out)
        
        return super(PythonService, self).start()
    
    def get_environ(self):
        environ = super(PythonService, self).get_environ()
        
        ### Put our virtual env in the environ
        if self.virtualenv:
            path = os.path.abspath(os.path.join(self.path, self.virtualenv))
            environ['VIRTUAL_ENV'] = path
            logging.info("Using virtualenv: %s", path)
            path_insert(environ, 'PATH', os.path.join(path, 'bin'))
        
        path_insert(environ, 'PYTHONPATH', os.path.abspath(os.curdir))
        path_insert(environ, 'PYTHONPATH', os.path.abspath(self.path))
        
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
        
        if "VIRTUAL_ENV" in os.environ:
            activate_this = os.path.join( os.environ['VIRTUAL_ENV'], 'bin', 'activate_this.py' )
            execfile(activate_this, dict(__file__=activate_this))
        
        return dct
