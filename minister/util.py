import os, traceback, sys, logging, re

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
    lines = ["\nError:\n"]
    lines.extend(traceback.format_tb(sys.exc_traceback)[1:])
    lines.append("%s: %s" % (e.__class__.__name__, str(e)))

    lines.append("\n\nLocals:\n")
    tb = sys.exc_info()[2]
    while tb.tb_next:
        tb = tb.tb_next
    frame = tb.tb_frame
    for key, value in frame.f_locals.items():
        try:
            value = "%r" % value
        except:
            value = '<not representable>'
        lines.append("\t%s: %s\n" % (key,value))

    print "".join(lines)