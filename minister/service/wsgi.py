import os, sys
import base

class Service(base.PythonService):
    type = 'wsgi:service'
    name = "Wsgi Service"
    args = [__file__]
    app = None
    num_process = 2


### Client Side #############################################
def resolve_app(sig):
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
    m = __import__(module, fromlist=[app])
    return getattr(m, app)


if __name__ == '__main__':
    settings = Service.setup_backend()
    
    from eventlet import wsgi
    wsgi.server(settings['socket'], resolve_app(settings['app']))
    
