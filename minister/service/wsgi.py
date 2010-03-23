import os, sys
import base

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


class Service(base.Service):
    type = 'wsgi'
    name = "Wsgi Service"
    args = [__file__]
    app = None


if __name__ == '__main__':
    settings = Service.setup_backend()
    
    print "Starting service."
    
    from eventlet import wsgi
    wsgi.server(settings['socket'], resolve_app(settings['app']))
    
