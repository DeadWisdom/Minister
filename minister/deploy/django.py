import os, sys
import base

class Deployment(base.Deployment):
    type = 'django'
    name = "Unnamed Django Deployment"
    settings = 'settings'
    args = [__file__]
    requires = base.Deployment.requires + ['django']
    
    def get_environ(self):
        env = super(Deployment, self).get_environ()
        env['DJANGO_SETTINGS_MODULE'] = self.settings
        return env

    def serve(self):
        from eventlet import wsgi, api
        from django.core.handlers.wsgi import WSGIHandler
        from django.core.servers.basehttp import AdminMediaHandler
        
        app = WSGIHandler()
        app = AdminMediaHandler(app)
    
        wsgi.server(self._socket, app, log=open(os.devnull, 'w'))

if __name__ == '__main__':
    sys.path.insert(0, os.environ['DEPLOY_PATH'])
    deployment = Deployment.rebuild()
    deployment.serve()