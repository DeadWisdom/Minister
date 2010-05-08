import os, sys
import base
from minister.util import shell

class Service(base.ProcessService):
    type = 'redis:service'
    name = "Redis Service"
    address = ('0.0.0.0', 0)
    source = "http://redis.googlecode.com/files/redis-1.2.6.tar.gz"
    count = 1
    executable = "redis-server"
    
    def start(self):
        out, err = shell(self.path, 'make')
        if out:
            logging.info('> make\n%s', out)
        
        return super(Service, self).start()