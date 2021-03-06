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
    url = None          # Accepts no url
    site = '*'          # Accepts any site
    disabled = False
    _manager = None
    
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if not k.startswith('_') and not hasattr(self.__class__, k):
                raise TypeError("%s.__init__ got an unexpected keyword argument %r" % (self.__class__.__name__, k))
            setattr(self, k, v)
        self.init()
    
    def __call__(self, environ, start_response):
        return None
    
    def init(self):
        pass
    
    @classmethod
    def get_class(cls, type, default=None):
        return __types__.get(type + ":" + cls.type, __types__.get(type, default))
    
    @classmethod
    def create(cls, properties):
        if properties is None:
            return ListLayout(resources=[])
        if isinstance(properties, Resource):
            return properties
        if isinstance(properties, list):
            instance = ListLayout(resources=[cls.create(o) for o in properties])
        else:
            type = cls.get_class(properties.get('type'), cls)
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
            return None
        if self.url == '*':
            return path
        if self.url is not None and path.startswith(self.url):
            return path[len(self.url):]
    
    def match_site(self, hostname):
        if self.site is None:
            return False
        if self.site == '*':
            return True
        if isinstance(self.site, basestring):
            return hostname == self.site
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
        requested_path = environ.get('PATH_INFO', '')
        hostname, _, _ = environ.get('HTTP_HOST').partition(":")
        for resource in self.resources:
            if resource.disabled:
                continue
            if not resource.match_site(hostname):
                continue
            delta = resource.match_path(requested_path)
            if delta is not None:
                environ['SCRIPT_NAME'] = environ['SCRIPT_NAME'] + requested_path[:len(requested_path)-len(delta)]
                environ['PATH_INFO'] = delta
                return resource(environ, start_response)
                
    def __getitem__(self, i):
        return self.resources[i]

    def __getslice__(self, *a):
        return self.resources.__getslice__(*a)

    def __iter__(self):
        return self.resources.__iter__()

    def append(self, resoure):
        self.resources.append(resoure)
        
    def insert(self, index, resource):
        self.resources.insert( index, resource )
    
    def extend(self, resources):
        self.resources.extend( resources )

    def __str__(self):
        return "%s : %s" % (self.__class__, self.resources)


class ListLayout(Layout):
    """ Like a layout, but simplifies to a list. """
    def simple(self):
        return [o.simple() for o in self.resources]


class App(Resource):
    """Turns any app into a resource."""
    type = 'app'
    app = None
    
    def __init__(self, **kw):
        super(App, self).__init__(**kw)
        if not self.app:
            raise TypeError("__init__ must specify an *app* keyword.")
    
    def __call__(self, environ, start_response):
        return self.app(environ, start_response)
