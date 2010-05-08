"""
PHP Service.
"""

import os, sys
import fastcgi, base

from eventlet.green import socket
from minister.static import Static

class Service(fastcgi.Service, base.ProcessService):
    type = 'php:service'
    address = ('127.0.0.1', 0)
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
        self._fastcgi = self._proxy
        del self._proxy
        
        self._static = Static(index=self.index, root=self.path, allow=None)
        self._static.set_handler('php', self._handle)
    
    def _proxy(self, environ, start_response):
        if 'REQUEST_URI' not in environ:
            # PHP likes to have this variable
            request_uri = [
                environ.get('SCRIPT_NAME', ''),
                environ.get('PATH_INFO', ''),
            ]
            if environ.get('QUERY_STRING'):
                request_uri.extend(['?', environ['QUERY_STRING']])
            environ['REQUEST_URI'] = "".join(request_uri)
            
        path = environ['PATH_INFO']
        if '.php/' in path:
            path, info = path.split('.php/', 1)
            environ['PATH_INFO'] = path + '.php'
            environ['minister.php_info'] = '/' + info
        
        response = self._static(environ, start_response)
        return response
        
    def _handle(self, environ, start_response, path):
        _SERVER = environ
        
        _SERVER['SCRIPT_NAME'] = environ['SCRIPT_NAME'] + environ['PATH_INFO'] 
        _SERVER['SCRIPT_FILENAME'] = path    
        _SERVER["DOCUMENT_ROOT"] = self.path
        _SERVER["SERVER_NAME"] = environ["HTTP_HOST"]
        
        if 'minister.php_info' in environ:
            _SERVER['PATH_INFO'] = environ['minister.php_info']
            del _SERVER['minister.php_info']
        else:
            _SERVER['PATH_INFO'] = ''
        
        if (environ['REQUEST_METHOD'] == 'POST' and not environ.get('CONTENT_TYPE')):
            _SERVER['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        
        response = self._fastcgi(_SERVER, start_response)
        return response
    
    def find_index(self, path):
        """Find an index file in the directory specified at path."""
        for i in self.index:
            candidate = os.path.join(path, i)
            if os.path.isfile(candidate):
                return candidate
        return None
    