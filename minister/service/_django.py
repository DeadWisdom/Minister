import os, sys
import base

class Service(base.PythonService):
    type = 'django:service'
    name = "Django Service"
    settings = 'settings'
    args = [__file__]
    requires = base.PythonService.requires + ['django']
    
    def get_environ(self):
        env = super(Service, self).get_environ()
        env['DJANGO_SETTINGS_MODULE'] = self.settings
        return env


if __name__ == '__main__':
    settings = Service.setup_backend()
    
    from eventlet import wsgi
    from django.core.handlers.wsgi import WSGIHandler
    from django.core.servers.basehttp import AdminMediaHandler
    
    app = WSGIHandler()
    app = AdminMediaHandler(app)

    wsgi.server(settings['socket'], app)