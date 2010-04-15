import os, simplejson

from minister import http
from minister.resource import Resource, Layout, App
from minister.static import Static
from minister.util import MutableFile, simple_template

from minister.service import base

MEDIA_PATH = os.path.abspath(
    os.path.join( os.path.dirname(__file__), 'media' )
)

class Service(base.Service):
    type = "admin"
    url = 'minister/'
    site = '*'
    layout = Layout(resources=[
        Static(url='static/', root=MEDIA_PATH, exclude=['index.html'], volatile=True),
    ])
    path = "@admin"
    name = "Admin"
    
    def init(self):
        self._index = MutableFile( os.path.join(MEDIA_PATH, 'index.html') )
        self.name = self.name
    
    def start(self):
        self.disabled = False
        
    def stop(self):
        self.disabled = True
        
    def check_status(self):
        if self.disabled:
            return "disabled"
        return "active"
    
    def __call__(self, environ, start_response):
        path = environ['PATH_INFO']
        if path == '':
            return self.main(environ, start_response)
        if path.startswith('services/'):
            environ['PATH_INFO'] = environ['PATH_INFO'][len('services/'):]
            return self.services(environ, start_response)
        return self.layout(environ, start_response)
    
    def main(self, environ, start_response):
        environ['_content'] = simple_template(self._index.read(), {'url': '/%s' % self.url})
        return http.Response()(environ, start_response)
    
    def services(self, environ, start_response):
        path = environ['PATH_INFO']
        if path == '*.json':
            root = os.path.abspath( self._manager.path )
            services = []
            for token in self._manager._tokens.values():
                services.append(token.info())
            services.sort(key=lambda x: x.get('name', '-'))
            content = simplejson.dumps(services)
            return http.Response(content=content, type='text/javascript')(environ, start_response)
    
    def simple(self):
        return Resource.simple(self)