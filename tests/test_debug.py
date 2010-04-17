#!/usr/bin/python
import sys, logging
from unittest import TestCase
from test_resource import TestResource
from minister.resource import Resource
from minister.debug import DebugNotFound, DebugInternalServerError

class MockManager(object):
    log = logging
    def __init__(self, address):
        self.resources = Resource.create([])
        self.services = Resource.create([])
        self.address = address

class TestManager(TestResource):
    manager = MockManager(('test_debug', '80'))
    
    def test_404(self):
        content, status, headers = self.mock_request(DebugNotFound(self.manager))
        self.assertEqual( status, '404 Not Found' )
        self.assertTrue( 'Available Resources' in content )
    
    def test_500(self):
        try:
            assert False
        except:
            exc = sys.exc_info()
        
        content, status, headers = self.mock_request(DebugInternalServerError(exc))
        self.assertEqual( status, '500 Internal Server Error' )
        self.assertTrue( 'AssertionError' in content )
