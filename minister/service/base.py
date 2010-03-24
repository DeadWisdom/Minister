import os, sys, signal, errno, time, logging, shlex

import eventlet
from eventlet.green import socket, subprocess

try:
    from minister.resource import Resource
    from minister.proxy import Proxy
    from minister.util import json, fix_unicode_keys, get_logger, FileLikeLogger
except ImportError:
    print os.environ
    raise RuntimeError("Unable to find minister in our environment.")

class Service(Resource):
    ### Properties #######################
    address = ('', 0)
    port_range = (10000, 20000)
    args = None
    before_deploy = []
    disabled = False
    environ = {}
    executable = sys.executable
    layout = None
    name = 'Unnamed Service'
    slug = None
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
    _manager = None
    
    ### Class Properties ##################]
    _used_addresses = set()

    ### Class Methods #####################
    @classmethod
    def setup_backend(cls, dct=None):
        """
        This is called by a backend (child) python process to setup the
        environment and create a simple object representing the service
        settings gleamed from the os.environ key SERVICE_JSON.
        """
        if dct is None:
            dct = fix_unicode_keys( json.loads(os.environ['SERVICE_JSON']) )
        
        if '_socket' in dct:
            dct['socket'] = socket.fromfd( dct['_socket'], socket.AF_INET, socket.SOCK_STREAM )
        
        if 'SERVICE_MANAGER_PATH' in os.environ:
            dct['logger'] = get_logger(path=os.environ['SERVICE_MANAGER_PATH'],
                                       name=dct['slug'],
                                       level=dct.get('log_level', cls.log_level),
                                       max_bytes=dct.get('log_max_bytes', cls.log_max_bytes),
                                       count=dct.get('log_count', cls.log_count),
                                       format=dct.get('log_format', cls.log_format),
                                       echo=dct.get('log_echo', cls.log_echo))
            dct['log'] = FileLikeLogger(dct['slug'])
        
        sys.path.insert(0, dct['path'])
        
        return dct
    
    ### Instance Methods ###################
    def __init__(self, **kw):
        super(Service, self).__init__(**kw)
        if self.slug.startswith('@'):
            self._log = logging.getLogger('minister')
        else:
            self._log = get_logger(path=self._manager.path,
                                   name=self.slug,
                                   level=self.log_level,
                                   max_bytes=self.log_max_bytes,
                                   count=self.log_count,
                                   format=self.log_format,
                                   echo=self.log_echo)
    
    def init(self):
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
            'SERVICE_MANAGER_PATH': self._manager.path,
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
            process = Process(self.path, self.executable, self.args, self.get_environ(), self._log)
            self._processes.append( process )
            process.run()
    
    def shell(self, cmd):
        log = self._log
        args = shlex.split(cmd)
        log.info("-", cmd)
        popen = subprocess.Popen(list(args), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = popen.communicate()
        
        if err:
            log.error('    ' + '    \n'.join([line for line in err.split('\n')]))
            
        if out:
            log.error('    ' + '    \n'.join([line for line in out.split('\n')]))
        
        return out or err
    
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
            if process.check():
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
                
    def find_port(self):
        host = self.address[0]
        for port in range(*self.port_range):
            if (host, port) in self._used_addresses:
                continue
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind((host, port))
            except socket.error, e:
                continue
            else:
                self._used_addresses.add((host, port))
                s.close()
                return host, port

class Process(object):
    """
    A wrapper around subprocess.Popen, but keeps track of the process, and
    allows you to check its status, rerun the process, and figure out if it
    has failed, meaning it has restarted 3 times in the past 30 seconds.
    """
    def __init__(self, path=None, executable=None, args=[], env={}, logger=None):
        self.pid = None
        self.path = os.path.abspath( path )
        self.executable = executable
        self.args = [executable] + args
        self.env = env
        self.logger = logger
        self.returncode = None
        
        self._popen = None
        self._starts = []   # We keep track of start times, so that we can
                            # tell how many times we restarted.
    
    def readloop(self):
        def outloop():
            while True:
                if not self._popen:
                    return
                line = self._popen.stdout.readline()
                if not line:
                    return
                self.logger.info(line[:-1])
        def errloop():
            while True:
                if not self._popen:
                    return
                line = self._popen.stderr.readline()
                if not line:
                    return
                self.logger.error(line[:-1])
        eventlet.spawn_n(outloop)
        eventlet.spawn_n(errloop)
    
    def run(self):
        """Run the process."""
        self._starts.append(time.clock())
        self._starts = self._starts[-3:]
        
        try:
            self._popen = subprocess.Popen(
                                self.args,
                                executable = self.executable,
                                stdout = subprocess.PIPE,
                                stderr = subprocess.PIPE,
                                shell = False,
                                cwd = self.path,
                                env = self.env)
        except OSError, e:
            logging.getLogger('minister').error("%s - %s", " ".join(self.args), e)
            return False
            
        self.readloop()
        return True
        
    def check(self):
        """
        Returns True if the process is running.  When it fails, the returncode
        will be available as the ``returncode`` attribute.
        """
        if (not self._popen):
            return False
        if self._popen.poll():
            self.returncode = self._popen.returncode
            self._popen = None
            return False
        return True
    
    def is_failure(self, leeway=30):
        """
        Return true if the process has started three times in the last 
        ``leeway`` seconds.
        """
        if len(self._starts) < 3:
            return False
        else:
            #It's a failure if the third to last run was less than <leeway> seconds ago.
            return (time.clock() - self._starts[-3]) < leeway
    
    def terminate(self):
        """
        Terminate the prorcess, sends SIGTERM.  On windows this is the same
        as kill().
        """
        if self._popen:
            self._popen.terminate()
    
    def kill(self):
        """
        Kills the prorcess, sends SIGKILL.  On windows this is the same
        as terminate().
        """
        if self._popen:
            self._popen.kill()
