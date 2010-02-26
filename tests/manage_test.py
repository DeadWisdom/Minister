#!/usr/bin/python
import os, eventlet

from unittest import TestCase
from minister.manager import Manager

class TestManager(TestCase):
    
    repo_path = os.path.join(__file__, '..', 'repo')
    
    def test_serve_and_close(self):
        manager = Manager(path=self.repo_path)
        eventlet.spawn_n(manager.serve)
        eventlet.sleep(.1)
        manager.close()