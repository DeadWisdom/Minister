import os, sys
import base

from eventlet.green import socket

class Deployment(base.Deployment):
    type = 'wsgi'
    name = "Unnamed Wsgi Deployment"
    address = None
    ini = None
    executable = "/usr/bin/php"
    environ = {'PHP_FCGI_CHILDREN': '0'}
    
    def init(self):
        raise NotImplementedError

        if self.address is None:
            self.address = ('', self.find_unused_port())
            
        args = []
        if self.ini is not None:
            args.extend(['-c', self.ini])
        
        self.args = " ".join(args)
    
    def find_unused_port(self, range=(5000, 6000)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        for port in range:
            try:
                sock.bind(('', port))
                sock.close()
                return port
            except socket.error:
                continue
        return None