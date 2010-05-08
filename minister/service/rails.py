import os, sys
import base

class Service(base.ProxyService, base.ProcessService):
    type = 'rails:service'
    name = "Rails Service"
    script = 'script/server'
    address = ('0.0.0.0', 0)
    
    def __init__(self, **kw):
        super(Service, self).__init__(**kw)
        if self.address[1] == 0:
            self.address = self.find_port()
            self._proxy = base.Resource.create({'type': 'proxy', 'address': self.address})
    
    def start(self):
        self.args = ['--binding', str(self.address[0]), '--port', str(self.address[1])]
        self.executable = os.path.join(self.path, self.script)
        super(Service, self).start()