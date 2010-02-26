import os
from eventlet import wsgi

def app(environ, start_response):
    start_response('200 OK', [])
    return ("Deployment - A\n\nPath: ", os.environ['DEPLOY_PATH'])