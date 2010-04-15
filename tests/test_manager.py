#!/usr/bin/python
import os, eventlet, random, json

from eventlet.green import urllib, socket
from unittest import TestCase
from minister.manager import Manager

class TestManager(TestCase):
    repo_path = os.path.join(__file__, '..', 'repo')
    
    def setUp(self):
        port = random.randint(10000, 12000)
        services = [{'type': 'admin', 'path': '@admin', 'url': 'admin/', 'site': '*'}]
        self.manager = Manager(path=self.repo_path, services=services, debug=True)
        eventlet.spawn(self.manager.serve, ('', port))
        eventlet.sleep(.1)
    
    def tearDown(self):
        self.manager.close()
    
    def test_admin(self):
        services = urllib.urlopen("http://%s:%s/admin/services/*.json" % self.manager.address).read()
        services = json.loads(services)
        services = dict((s['slug'], s) for s in services)
        
        admin = services['@admin']
        self.assertEqual(admin['path'], '@admin')
        self.assertEqual(admin['url'], 'admin/')
        self.assertEqual(admin['status'], 'active')