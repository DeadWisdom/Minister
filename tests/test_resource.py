#!/usr/bin/python
import os, eventlet, random, json

from eventlet.green import urllib, socket
from unittest import TestCase
from minister.resource import Resource, Simple

def mock_start_response(result):
    def start_response(status, headers):
        result['status'] = status
        result['headers'] = headers
    return start_response

class TestManager(TestCase):
    repo_path = os.path.join(__file__, '..', 'repo')

    def mock_request(self, resource, **envvars):
        env = {
            'PATH_INFO': '',
            'SCRIPT_NAME': '',
            'HTTP_HOST': 'mock_request:80',
        }
        env.update(envvars)
        sh = {'status': '404 Not Found', 'headers': []}
        def start_response(status, headers):
            sh['status'], sh['headers'] = status, headers
        content = resource(env, start_response)
        if content is not None:
            content = "".join(content)
        return content, sh['status'], sh['headers']
    
    def test_resource(self):
        r = Resource(url='r/', site="*")
        
        self.assertEqual( r.match_path('r/'), "" )
        self.assertTrue( r.match_site('anything') )
    
        # If we add a keyword argument that isn't allowed, a TypeError is raised.
        self.assertRaises( TypeError, Resource, not_a_key = True )
    
    def test_site(self):
        host_a = Resource(url='', site='host_a')
        host_b = Resource(url='', site='host_b')
        host_a_or_b = Resource(url='', site=['host_a', 'host_b'])
        anything = Resource(url='', site='*')
        host_none = Resource(url='', site=None)
        
        self.assertTrue( host_a.match_site('host_a') )
        self.assertFalse( host_a.match_site('host_b') )
        
        self.assertFalse( host_b.match_site('host_a') )
        self.assertTrue( host_b.match_site('host_b') )
        
        self.assertTrue( host_a_or_b.match_site('host_a') )
        self.assertTrue( host_a_or_b.match_site('host_a') )
        self.assertFalse( host_a_or_b.match_site('host_z') )
        
        self.assertTrue( anything.match_site('host_a') )
        self.assertTrue( anything.match_site('host_b') )
        self.assertTrue( anything.match_site('host_z') )
        
        self.assertFalse( host_none.match_site('host_a') )
        self.assertFalse( host_none.match_site('host_b') )
        self.assertFalse( host_none.match_site('host_z') )
    
    def test_create(self):
        r = Resource.create({
            "type": "simple"
        })
        
        self.assertEqual(r.__class__, Simple)
    
    def test_simple(self):
        r = Simple(
            content="Hello", 
            headers=[("header", "yes")]
        )
        
        content, status, headers = self.mock_request(r)
        
        self.assertEqual( status, "200 OK" )
        self.assertEqual( headers, [("header", "yes")])
        self.assertEqual( content, "Hello" )
    
    def test_layout(self):
        r = Resource.create([
            Simple( content="A", url = "a/" ),
            Simple( content="B", url = "b/" ),
        ])
        
        result = {}
        content, status, _ = self.mock_request(r, PATH_INFO='a/')
        self.assertEqual( status, "200 OK")
        self.assertEqual( content, "A")
        content, status, _ = self.mock_request(r, PATH_INFO='b/')
        self.assertEqual( status, "200 OK")
        self.assertEqual( content, "B")
        _, status, _ = self.mock_request(r, PATH_INFO='favicon.ico')
        self.assertEqual( status, "404 Not Found")
        
    def test_app(self):
        def app(environ, start_response):
            start_response("200 OK", [])
            return ("App!",)
        
        r = Resource.create({
            'type': 'app',
            'app': app
        })
    
        content, _, _ = self.mock_request(r)
        self.assertEqual( content, "App!" )
