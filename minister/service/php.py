"""
PHP Service.
"""

import os, sys
import fastcgi

from eventlet.green import socket
from minister.static import Static
from minister.http import Http404

class Service(fastcgi.Service):
    type = 'php'
    address = ('127.0.0.1', 0)
    port_range = (10000, 20000)
    executable = 'php-cgi'
    ini = None
    options = {}
    num_processes = 1
    index = ('index.php', 'index.html')
    
    def init(self):
        if (self.address[1] == 0):
            self.address = self.find_port()
        if not self.args:
            self.args = ['-b', '%s:%s' % self.address]
            if self.ini:
                self.args.extend(['-c', self.ini])
            for pair in self.options.items():
                self.args.extend(['-d', '%s=%s' % pair])
        
        super(Service, self).init()
        
        self._static = Static(index=self.index, root=self.path)
        self._static.set_handler('php', self._handle)
    
    def _proxy(self, environ, start_response):
        path = environ.get('SCRIPT_NAME', environ.get('PATH_INFO', ''))
        if '.php/' in path:
            path, info = path.split('.php/', 1)
            environ['SCRIPT_NAME'] = path + '.php'
            environ["PATH_INFO"] = '/' + info
        
        return self._static(environ, start_response)
        
    def _handle(self, environ, start_response, path):
        environ['SCRIPT_NAME'] = path
        
        if 'REQUEST_URI' not in environ:
            # PHP likes to have this variable
            request_uri = [
                environ.get('SCRIPT_NAME', ''),
                environ.get('PATH_INFO', ''),
            ]
            if environ.get('QUERY_STRING'):
                request_uri.extend(['?', environ['QUERY_STRING']])
            environ['REQUEST_URI'] = "".join(request_uri)
        
        if '/' in path:
            environ['SCRIPT_FILENAME'] = path.rsplit('/', 1)[1]
        else:
            environ['SCRIPT_FILENAME'] = path
        
        return self._resource(environ, start_response)
    
    def find_port(self):
        host = self.address[0]
        for port in range(*self.port_range):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind((host, port))
            except socket.error, e:
                continue
            else:
                s.close()
                return host, port
    
    def find_index(self, path):
        """Find an index file in the directory specified at path."""
        for i in self.index:
            candidate = os.path.join(path, i)
            if os.path.isfile(candidate):
                return candidate
        return None