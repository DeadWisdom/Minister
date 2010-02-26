import os, sys
import base

class Deployment(base.Deployment):
    type = 'wsgi'
    name = "Unnamed Wsgi Deployment"
    args = [__file__]
    app = None
    
    def resolve_app(self):
        sig = self.app
        if sig is None:
            raise RuntimeError("No app has been specified.")
        if callable(sig):
            return sig
        module, app = sig.rsplit('.', 1)
        m = __import__(module, fromlist=[app])
        return getattr(m, app)
    
    def serve(self):
        from eventlet import wsgi, api
        wsgi.server(self._socket, self.resolve_app())

if __name__ == '__main__':
    sys.path.insert(0, os.environ['DEPLOY_PATH'])
    deployment = Deployment.rebuild()
    deployment.serve()
