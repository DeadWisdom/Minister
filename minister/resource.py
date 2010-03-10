"""
    Resources are the key building blocks.
    They have the following properties:
        - Each is a mini wisgi app in itself.
        - They have class-level attributes that carry defaults.
        - Each class-level attribute can be over-written on an instance by passing
          said attribute in as a keyword argument to __init__. Note: This does not 
          apply to attributes starting with an underscore ('_').
        - __init__ will call the convenient 'init()' method after it has set up
          the instance's attributes.
"""

__types__ = {}

class ResourceMeta(type):
    def __new__(meta, classname, bases, classDict):
        cls = type.__new__(meta, classname, bases, classDict)
        _type = classDict.get('type', None)
        if _type:
            __types__[_type] = cls
        return cls

class Resource(object):
    __metaclass__ = ResourceMeta
    
    type = 'resource'
    url = None          # Accepts any url
    site = None        # Accepts any site
    disabled = False
    _manager = None
    
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if not k.startswith('_') and not hasattr(self.__class__, k):
                raise TypeError("__init__ got an unexpected keyword argument %r" % k)
            setattr(self, k, v)
        self.init()
    
    def __call__(self, environ, start_response):
        return None
    
    def init(self):
        pass
    
    @classmethod
    def get_class(cls, type, default=None):
        return __types__.get(type, default)
    
    @classmethod
    def create(cls, properties):
        if properties is None:
            return None
        if isinstance(properties, Resource):
            return properties
        if isinstance(properties, list):
            instance = ListLayout(resources=[cls.create(o) for o in properties])
        else:
            type = Resource.get_class(properties.get('type'), cls)
            if not type:
                raise RuntimeError("Unnable to find type:", type)
            instance = type(**properties)
        return instance

    def simple(self):
        simple = {'type': self.type}
        for k, v in self.__dict__.items():
            if k.startswith('_'): continue
            if isinstance(v, Resource):
                simple[k] = v.simple()
            elif hasattr(v, '__iter__') and not isinstance(v, basestring):
                try:
                    simple[k] = [o.simple() for o in v]
                except:
                    simple[k] = v
            else:
                simple[k] = v
        return simple
    
    def match_path(self, path):
        if self.url is None:
            return path
        if self.url is not None and path.startswith(self.url):
            return path[len(self.url):]
    
    def match_site(self, hostname):
        if self.site is None:
            return True
        if hostname in self.site:
            return True

class Simple(Resource):
    type = 'simple'
    status = '200 OK'
    headers = []
    content = ''

    def __call__(self, environ, start_response):
        start_response(self.status, self.headers)
        return (self.content, )


class Layout(Resource):
    type = 'layout'
    resources = []
    
    def __call__(self, environ, start_response):
        requested_path = environ.get('PATH_DELTA', environ.get('PATH_INFO', ''))
        hostname, _, _ = environ.get('HTTP_HOST').partition(":")
        for resource in self.resources:
            if resource.disabled:
                continue
            if not resource.match_site(hostname):
                continue
            delta = resource.match_path(requested_path)
            if delta is not None:
                environ['PATH_DELTA'] = delta
                response = resource(environ, start_response)
                environ['PATH_DETLA'] = requested_path
                return response
    
    def add(self, resoures):
        self.resources += list(resoures)

class ListLayout(Layout):
    """ Like a layout, but simplifies to a list. """
    def simple(self):
        return [o.simple() for o in self.resources]

class App(Resource):
    """Turns any app into a resource."""
    type = 'app'
    app = None
    
    def init(self):
        if not self.app:
            raise TypeError("__init__ must specify an *app* keyword.")
    
    def __call__(self, environ, start_response):
        return self.app(environ, start_response)

