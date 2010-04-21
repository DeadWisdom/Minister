import re
from minister.resource import Resource

class Middleware(Resource):
    type = "middleware"
    url = "*"
    site = "*"
    processor = None
    
    def __call__(self, next):
        return self.resolve_app(self.processor)(next)
        
    def start_response_with_headers(self, start_response, extra_headers):
        def _wrapped_start_response(status, headers, *a, **ka):
            headers = list(headers) + list(extra_headers)
            return start_response(status, headers, *a, **ka)
        return _wrapped_start_response
    
    def set_manager(self, manager):
        self._manager = manager
    
    def resolve_app(self, sig):
        """
        Resolves the app function based on an import string:
    
        >>> resolve_app('wsgi.resolve_app') == resolve_app
        True
        """
        if sig is None:
            raise RuntimeError("No app has been specified.")
        if callable(sig):
            return sig
        
        module, app = sig.rsplit('.', 1)
        if self._manager:
            sys.path.insert(0, self._manager.path)
            m = __import__(module, fromlist=[app])
            sys.path.pop(0)
        else:
            m = __import__(module, fromlist=[app])
        return getattr(m, app)


class Rewrite(Middleware):
    type = "rewrite:middleware"
    rules = []
    
    def __init__(self, **ka):
        super(Rewrite, self).__init__(**ka)
        self.rules = [(re.compile(k), v) for k, v in self.rules]
    
    def __call__(self, next):
        def app(environ, start_response):
            path = environ['PATH_INFO']
            for regex, result in self.rules:
                m = regex.match(path)
                if m:
                    environ['PATH_INFO'] = m.expand(result)
                    break
            return next(environ, start_response)
        return app
    