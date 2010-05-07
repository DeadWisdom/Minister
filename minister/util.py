import os, traceback, sys, re, shlex
import logging, logging.handlers
from eventlet.green import subprocess

try:
    import json
except ImportError:
    import simplejson as json
    

class MutableFile(object):
    def __init__(self, path):
        self.path = path
        self.mtime = -1
        self.read()
    
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
            file = open(self.path)
            try:
                self.cache = file.read()
            finally:
                file.close()
        return self.cache

def path_insert(dct, k, v):
    if k in dct:
        dct[k] = "%s:%s" % (v, dct[k])
    else:
        dct[k] = v

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

def shell(path, cmd):
    args = shlex.split(str(cmd))
    try:
        popen = subprocess.Popen(list(args), cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = popen.communicate()
    except OSError, e:
        err = str(e)
        out = None
    
    return out, err

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

class FileLikeLogger(object):
    """Acts like a file, but just logs to the logger."""
    def __init__(self, name=None, level="info"):
        if name:
            self.logger = logging.getLogger(name)
        else:
            self.logger = logging.getLogger()
        self.level = level
    
    def write(self, output):
        getattr(self.logger, self.level)(output.strip())