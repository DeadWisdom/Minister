import os, sys, logging

import eventlet
from eventlet import wsgi
from eventlet.green import socket

from http import NotFound, InternalServerError, BadGateway
from debug import DebugNotFound, DebugInternalServerError
from resource import Resource
from tokens import ServiceToken
from service import Service
from util import json, FileLikeLogger

class Manager(Resource):
    type = 'manager'
    path = None
    resources = []
    services = []
    debug = False
    address = None
    
    def init(self):
        self.path = os.path.abspath(self.path)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        
        self._threads = []
        self._socket = None
        
        self._token_map = {}
        self._paths = set()
        
        self.services, services = [], self.services
        for s in services:
            self.add_service(s['path'], s)
            
        self.resources = Resource.create(self.resources)
        
        for service in self.services:
            logging.info("loading service: %s", service.path)
            service.deploy()
            
        service_path = os.path.join(self.path, 'services')
        if not os.path.exists(service_path):
            os.makedirs(service_path)
        
        self.periodically(self.scan, 1)
        self.periodically(self.update, 60 * 30)
    
    def save(self):
        file = open(os.path.join(self.path, 'config.json'), 'w')
        try:
            json.dump(self.simple(), file, indent=4)
        finally:
            file.close()
    
    def close(self):
        while self._threads:
            eventlet.kill( self._threads.pop() )
        self._socket = None
        for service in self.services:
            try:
                service.withdraw()
            except:
                pass
    
    @classmethod
    def listen(cls, address):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(address)
        sock.listen(500)
        return sock
    
    def serve(self, where=('', 8000), debug=False):
        if self._socket:
            return
        
        try:
            if isinstance(where, socket.socket):
                self._socket = where
            else:
                self._socket = self.listen(where)
            
            self.address = self._socket.getsockname()
            
            print "Manager servering on http://%s:%s" % self.address
            logging.info("manager serving on http://%s:%s", *self.address)
            wsgi.server(self._socket, self, log=FileLikeLogger())
        finally:
            self.close()
        
    def __call__(self, environ, start_response):
        environ['ORIG_PATH_INFO'] = environ['PATH_INFO']
        environ['SCRIPT_NAME'] = '/'
        environ['PATH_INFO'] = environ['PATH_INFO'][1:]
        
        try:
            response = self.resources(environ, start_response)
            if response is not None:
                return response
            
            requested_path = environ.get('PATH_INFO', '')
            hostname, _, _ = environ.get('HTTP_HOST').partition(":")
            for service in self.services:
                if service.disabled or not service.service:
                    continue
                if not service.match_site(hostname):
                    continue
                delta = service.match_path(requested_path)
                if delta is not None:
                    logging.debug("request sent to %s: %s", service.slug, environ['ORIG_PATH_INFO'])
                    if service.status == 'failed':
                        return BadGateway(msg="Service failed, unnable to continue request.")(environ, start_response)
                    environ['SCRIPT_NAME'] = environ['SCRIPT_NAME'] + requested_path[:len(requested_path)-len(delta)]
                    environ['PATH_INFO'] = delta
                    response = service(environ, start_response)
                    if response is not None:
                        return response
                    
        except Exception, e:
            if self.debug:
                exc_info = sys.exc_info()
                return DebugInternalServerError(exc_info=exc_info)(environ, start_response)
            else:
                return InternalServerError()(environ, start_response)
        
        logging.debug("Resource not found: %s", environ['ORIG_PATH_INFO'])
        
        if self.debug:
            return DebugNotFound(self)(environ, start_response)
        else:
            return NotFound()(environ, start_response)
    
    def periodically(self, method, interval=1):
        def loop():
            while True:
                method()
                eventlet.sleep(interval)
        self._threads.append( eventlet.spawn(loop) )
    
    def update(self):
        for service in self.services:
            print "Updating services..."
            if service.status in ("active", "failed", "disabled", "mia"):
                try:
                    if service.check_source():
                        logging.info("reloading service: %s", service.path)
                        service.redeploy()
                except Exception, e:
                    logging.exception("error updating service (%s): %s", service.slug, e)
    
    def get_service(self, k):
        return self._token_map[k]
    
    def add_service(self, path, override=None):
        t = ServiceToken(self, path, override)
        self._token_map[t.slug] = t
        self._paths.add(path)
        self.services.append(t)
        return t
    
    def has_service(self, path):
        return path in self._paths
    
    def scan(self):
        service_path = os.path.join(self.path, 'services')
        new = []
        for filename in os.listdir( service_path ):
            path = os.path.join(service_path, filename)
            if os.path.isdir(path) and not self.has_service(path):
                s = self.add_service(path)
                new.append(s)
                if s.is_valid():
                    s.deploy()
        if new:
            self.save()
            logging.info("new services found: \n   %s", "\n   ".join([s.path for s in new]))
    
