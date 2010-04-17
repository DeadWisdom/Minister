#!/usr/bin/python
import os, eventlet, random, json

from eventlet.green import socket, httplib
from unittest import TestCase
from minister.manager import Manager

class TestManager(TestCase):
    repo_path = os.path.join(__file__, '..', 'repo')
    
    def request(self, path, method='GET', params=None, headers={}):
        conn = httplib.HTTPConnection("%s:%s" % self.manager.address)
        conn.request(method, path, params, headers)
        return conn.getresponse()
    
    def setUp(self):
        port = random.randint(10000, 12000)
        services = [{'type': 'admin', 'path': '@admin', 'url': 'admin/', 'site': '*'}]
        self.manager = Manager(path=self.repo_path, services=services, debug=True)
        eventlet.spawn(self.manager.serve, ('', port))
        eventlet.sleep(.03)     #Give it some time to get on its feet.
    
    def tearDown(self):
        self.manager.close()
    
    def test_admin(self):
        response = self.request("/admin/services/*.json")
        services = json.load(response)
        services = dict((s['slug'], s) for s in services)
        
        admin = services['@admin']
        self.assertEqual(admin['path'], '@admin')
        self.assertEqual(admin['url'], 'admin/')
        self.assertEqual(admin['status'], 'active')
    
    def test_a(self):
        a = self.manager.get_service('a')
        
        self.assertEqual(a.status, 'active')
        
        request = self.request("/a/simple")
        self.assertEqual(request.status, 200)
        self.assertEqual(request.read(), "Simple Resource A")
        
        request = self.request("/a/")
        self.assertTrue( request.read().startswith( "Deployment - A\n\nPath: " ) )
    
    def test_b(self):
        request = self.request("/b/")
        self.assertEqual(request.status, 404)
        
    def test_d(self):
        self.assertEqual(self.manager.get_service('d').status, 'mia')
        