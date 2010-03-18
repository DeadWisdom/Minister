import os
from eventlet import wsgi

def app(environ, start_response):
    start_response('200 OK', [])
    if environ['PATH_INFO'] == "health":
        print "My health? Ain't good!"
        raise Exception("Health")
    return ("Deployment - A\n\nPath: ", os.environ['SERVICE_PATH'])