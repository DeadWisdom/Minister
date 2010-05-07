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
    def init(self):
        self._resource = FastCGI(address=self.address, filter=self.filter)
    
    def _proxy(self, environ, start_response):
        self._resource(environ, start_response)