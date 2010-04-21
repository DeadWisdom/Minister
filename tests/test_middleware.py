#!/usr/bin/python
import os, logging
from unittest import TestCase
from minister.service import base
from minister.resource import Resource

import eventlet
from eventlet import wsgi
from eventlet.greenio import socket
from eventlet.green import httplib
from eventlet.timeout import Timeout

class MockManager(object):
    log = logging
    path = os.path.join(__file__, '..', 'repo')

class MockResponse(object):
    pass

class TestServices(TestCase):
    path = os.path.abspath(os.path.join(__file__, '..', 'repo', 'services', 'a'))
    mock_manager = MockManager()
    
    def test_base(self):
        resources = [{'type': 'simple', 'content': 'simple', 'url': 'simple/'}]
        middleware = [{'type': 'rewrite', 'rules': [(r'(.*?)\.html', r'\1/')]}]
        service = base.Service(
            path = self.path, 
            resources = resources,
            middleware = middleware,
        )
        
        response = MockResponse()
        def start_response(status, headers):
            print status, headers
            response.status = status
            response.headers = headers
        
        app = service.get_app()
        
        env = { 'PATH_INFO': 'simple/', 
                'HTTP_HOST': 'localhost',
                'SCRIPT_NAME': '/' }
        content = app(env, start_response)
        self.assertTrue( content )
        self.assertEqual( response.status, '200 OK' )
        
        env = { 'PATH_INFO': 'simple.html', 
                'HTTP_HOST': 'localhost',
                'SCRIPT_NAME': '/' }
        content = app(env, start_response)
        self.assertTrue( content )
        self.assertEqual( response.status, '200 OK' )
        
        ## Sanity check.
        env = { 'PATH_INFO': 'not-there.wrong', 
                'HTTP_HOST': 'localhost',
                'SCRIPT_NAME': '/' }
        content = app(env, start_response)
        self.assertFalse( content )
        self.assertEqual( response.status, '200 OK' )
        