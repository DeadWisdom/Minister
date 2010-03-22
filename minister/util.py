import os, traceback, sys, re
import logging, logging.handlers

try:
    import json
except ImportError:
    import simplejson as json

class MutableFile(object):
    def __init__(self, path):
        self.path = path
        self.mtime = os.stat(path).st_mtime
        self.cache = open(self.path).read()
    
    def is_stale(self):
        try:
            mtime = os.stat(self.path).st_mtime
        except:
            return True
        if mtime > self.mtime:
            self.mtime = mtime
            return True
        return False
    
    def read(self):
        if self.is_stale():
            self.cache = open(self.path).read()
        return self.cache

def system(path, cmd, args):
    from eventlet.processes import Process
    print ">", path, cmd, " ".join(args)
    curdir = os.path.abspath(os.curdir)
    os.chdir(path)
    p = Process(cmd, args)
    result = p.wait()
    content = p.read()
    os.chdir(curdir)
    print content
    return result, content

def fix_unicode_keys(o):
    """
    Fixes all key, value pairs to be str(key), value pairs.
    """
    if isinstance(o, dict):
        return dict( (str(k), fix_unicode_keys(v)) for k, v in o.items() )
    elif hasattr(o, '__iter__') and not isinstance(o, basestring):
        return [ fix_unicode_keys(v) for v in o ]
    return o

def simple_template(string, context):
    def repl(m):
        return context[m.group(1).strip()]
    return re.sub('{{(.*?)}}', repl, string)

def print_tb(e):
    info = error_info(e)
    lines = ["\nError:\n"]
    lines.extend(info['traceback'])
    lines.append(info['exception'])
    
    lines.append("\n\nLocals:\n")
    for k, v in info['locals']:
        lines.append("\t%s: %s\n" % (k, v))

    print "".join(lines)

def error_info(e):
    info = {}
    info['traceback'] = traceback.format_tb(sys.exc_traceback)
    info['exception'] = "%s: %s" % (e.__class__.__name__, str(e))
    
    info['locals'] = []
    tb = sys.exc_info()[2]
    while tb.tb_next:
        tb = tb.tb_next
    frame = tb.tb_frame
    for key, value in frame.f_locals.items():
        try:
            value = "%r" % value
        except:
            value = '<not representable>'
        info['locals'].append( (key, value) )

    return info

def render_error(start_response, environ, error):
    start_response(error, [])

def get_logger(path=None, name=None, level=None, max_bytes=None, count=None, format=None, echo=None):
    path = os.path.join(path, 'logs', name + ".log")
    base = os.path.dirname(path)
    if not os.path.isdir(base):
        os.makedirs(base)
    
    logger = logging.getLogger(name)
    logger.setLevel(0)

    formatter = logging.Formatter(format)
    
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=max_bytes, backupCount=count)
    handler.setLevel(getattr( logging, level.upper() ))
    handler.setFormatter(formatter)
    logger.addHandler( handler )
    
    if (echo):
        handler = logging.StreamHandler()
        if isinstance(echo, basestring):
            handler.setLevel(getattr( logging, echo.upper() ))
        else:
            handler.setLevel(getattr( logging, level.upper() ))
        handler.setFormatter(formatter)
        logger.addHandler( handler )    
    
    return logger

class FileLikeLogger(object):
    """Acts like a file, but just logs to the logger."""
    def __init__(self, name, level="info"):
        self.logger = logging.getLogger(name)
        self.level = level
    
    def write(self, output):
        getattr(self.logger, self.level)(output.strip())
        

### Create the root logger that does nothing. ###
class NullHandler(logging.Handler):
    def emit(self, record):
        pass

root = logging.getLogger()
root.addHandler(NullHandler())
root.setLevel(0)
