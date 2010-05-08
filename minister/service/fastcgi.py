import os, sys
import base

from eventlet.green import socket
from minister.fastcgi import FastCGI
from minister.resource import Resource

class Service(base.ProxyService):
    ### Properties #########################
    type = 'fastcgi:service'
    executable = None
    requires = []
    name = "Unnamed FCGI Service"
    num_processes = 1
    filter = False
    
    ### Instance Methods ###################
    def start(self):
        super(base.ProxyService, self).start()
        self._proxy = FastCGI(address=self.address, filter=self.filter)
    
    def __call__(self, environ, start_response):
        """
        For use as a wsgi app, will pipe to our proxy.
        """
        response = super(Service, self).__call__(environ, start_response)
        if response is not None:
            return response
        return self._proxy(environ, start_response)