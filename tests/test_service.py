#!/usr/bin/python
import os
from unittest import TestCase
from minister.service import base
from minister.resource import Resource

import eventlet
from eventlet import wsgi
from eventlet.greenio import socket
from eventlet.green import httplib
from eventlet.timeout import Timeout


class MockManager(object):
    path = os.path.join(__file__, '..', 'repo')

class TestServices(TestCase):
    path = os.path.abspath(os.path.join(__file__, '..', 'repo', 'services', 'a'))
    mock_manager = MockManager()
    
    def request(self, address, path, method='GET', params=None, headers={}):
        t = Timeout(2, RuntimeError("Timeout trying to send request."))
        try:
            conn = httplib.HTTPConnection("%s:%s" % address)
            conn.request(method, path, params, headers)
        finally:
            t.cancel()
        return conn.getresponse()
    
    def test_base(self):
        resources = [{'type': 'simple', 'content': 'simple', 'url': ''}]
        service = base.Service(
            path=self.path, 
            resources=resources,
            before_deploy=["ls -asl"]
        )
        
        self.assertEqual( service.resources[0].type, 'simple' )
        self.assertTrue( service.start() )
        self.assertTrue( service.get_health()[0] )
    
        service.stop()
        
        self.assertFalse( service.get_health()[0] )
    
    def test_proxy(self):
        service = base.ProxyService(
            path = self.path,
            address = ('google', 80)
        )
        
        self.assertTrue( service.start() )
        service.stop()
    
    def test_process(self):
        service = base.ProcessService(
            path = self.path,
            args = ["-asl"],
            executable = "ls",
            _manager = self.mock_manager
        )
        
        self.assertTrue( service.start() )
        self.assertTrue( service.get_environ()['PATH'].startswith(self.path))
        service.stop()
    
    def test_python(self):
        env = os.path.join(self.path, 'env')
        this_repo = os.path.abspath(os.path.join(__file__, '..', '..'))
        
        service = base.PythonService(
            _manager = self.mock_manager,
            path = self.path,
            args = ["-c", 'import sys;print sys.executable'],
            executable = "python",
            requires = ["--no-deps -e git+%s#egg=minister" % this_repo],
            count = 2,
        )
        
        self.assertTrue( service.start() )
        self.assertTrue( service.get_environ()['PATH'].startswith(self.path))
        self.assertTrue( os.path.exists(env) )
        self.assertEqual( len(service._processes), 2 )
        service.stop()
    
    def test_wsgi(self):
        from minister.service import wsgi
        
        service = wsgi.Service(
            address = ('localhost', 0),
            _manager = self.mock_manager,
            path = self.path,
            app = "serve.app",
            virtualenv = None,
            count = 1
        )
        
        self.assertTrue( service.start() )
        
        eventlet.sleep(.3) # Give the processes some time to start
        
        self.assertTrue( service.get_health(True)[0] )
        
        response = self.request(service.address, "")
        self.assertTrue( response.status, 200 )
        self.assertEqual( response.read(), "Deployment - A\n\nPath: /Users/deadwisdom/projects/minister/tests/repo/services/a" )
        
        service.stop()
        
    def test_simple(self):
        from minister.service import wsgi
        
        service = wsgi.Service(
            address = ('localhost', 0),
            _manager = self.mock_manager,
            path = self.path,
            app = "serve.app",
            virtualenv = None,
            count = 1
        )
        
        simple = service.simple()
        self.assertEqual( simple.get('manager'), None )