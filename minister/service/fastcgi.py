import os, sys
import base

from eventlet.green import socket
from minister.fastcgi import FastCGI
from minister.resource import Resource

class Service(base.Service):
    ### Properties #########################
    type = 'fastcgi:service'
    address = ('', 0)
    executable = None
    requires = []
    name = "Unnamed FCGI Service"
    num_processes = 1
    filter = False
    
    ### Instance Methods ###################
    def init(self):
        self._proxy = FastCGI(address=self.address, filter=self.filter)
    
    def __call__(self, environ, start_response):
        """
        For use as a wsgi app, will pipe to our proxy.
        """
        response = super(Service, self).__call__(environ, start_response)
        if response is not None:
            return response
        return self._proxy(environ, start_response)