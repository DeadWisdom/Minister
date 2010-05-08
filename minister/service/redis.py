import os, sys
import base

class Service(base.ProcessService):
    type = 'redis:service'
    name = "Redis Service"
    address = ('0.0.0.0', 0)
    source = "http://redis.googlecode.com/files/redis-1.2.6.tar.gz"
    count = 1
    executable = "redis-server"
    before_deploy = ["make"]