#!/usr/bin/python
import os, logging
from unittest import TestCase
from minister.resource import Resource
from minister.tokens import ServiceToken

import eventlet
from eventlet.greenio import socket
from eventlet.green import httplib
from eventlet.timeout import Timeout

class MockManager(object):
    log = logging
    path = os.path.join(__file__, '..', 'repo')
    tokens = []

class TestTokens(TestCase):
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
    
    def test_tokens(self):
        t = ServiceToken(self.mock_manager, self.path, {
            'address': ('localhost', 0),
            'app': "serve.app",
            'count': 1,
            'type': 'wsgi',
            'virtualenv': None,
        })
        
        from minister.service import wsgi
        
        t.deploy()
        eventlet.sleep(.3)
        
        self.assertEqual(t.service.__class__, wsgi.Service)
        
        response = self.request(t.service.address, "")
        self.assertTrue( response.status, 200 )
        self.assertTrue( response.read().startswith("Deployment - A\n") )
        
        t.withdraw()
        