import os
from resource import Resource

class Logger(Resource):
    type = "logger"
    
    path = None
    debug = False
    info = True
    fileno = None
    
    def init(self):
        if self.fileno is not None:
            self._file = os.open(self.fileno)
        else:
            self._file = open(self.path, 'a')
            self.fileno = self._file.fileno()
        
    def write(self, string):
        self._file.write(string)
    
    def log(self, string, tag=''):
        if tag:
            self._file.write("[%s] - %s\n" % (tag, string))
        else:
            self._file.write("%s\n" % string)
    
    def debug(self, string):
        if self.debug:
            self.log(string, 'debug')
        
    def info(self, string):
        if self.info:
            self.log(string, 'info')