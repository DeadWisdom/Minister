#!/usr/bin/env python
import time, eventlet
from eventlet.timeout import with_timeout, Timeout
from eventlet.green import httplib

### Support ###
logfile = open("requests.log", "w")
def log(line):
    logfile.write(line + '\n')
    
server_ip = open('server.ip').read()

### Main ###
def send_request(timeout):
    try:
        start = time.clock()
        server = httplib.HTTPConnection(server_ip.strip())
        with_timeout(timeout, server.request, 'GET', '/')
        delta = time.clock() - start
        response = server.getresponse()
        assert response.status == 200
        assert response.read() == 'Pong!'
        log(str(delta))
    except Timeout:
        log('-')
    except AssertionError:
        log('!')

pool = eventlet.GreenPool(10000)
for i in xrange(50):
    log('# %d' % i)
    for i in xrange(10 * i):
        pool.spawn(send_request, 1)
    pool.waitall()

logfile.close()