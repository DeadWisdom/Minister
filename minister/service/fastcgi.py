import os, sys
import base

from eventlet.green import socket
from minister.fastcgi import FCGI

class Service(base.Service):
    ### Properties #########################
    type = 'fastcgi'
    executable = None
    requires = []
    name = "Unnamed FCGI Service"
    num_processes = 1
    filter = False
    
    ### Instance Methods ###################
    def init(self):
        self._resource = FCGI(self.address, self.filter)
        self.layout = Resource.create(self.layout)
    
    def _proxy(self, environ, start_response):
        self._resource(environ, start_response)