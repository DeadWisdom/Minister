"""
Daemonization utilities.  Taken heavily from:
http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

Thank you Sander Marechal
"""

import sys, os, time, atexit, signal, eventlet
from signal import SIGTERM 

def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
    """
    do the UNIX double-fork magic, see Stevens' "Advanced 
    Programming in the UNIX Environment" for details (ISBN 0201563177)
    http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
    """
    try: 
        pid = os.fork() 
        if pid > 0:
            # exit first parent
            sys.exit(0) 
    except OSError, e: 
        sys.stderr.write("daemonize fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/") 
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork() 
        if pid > 0:
            # exit from second parent
            sys.exit(0) 
    except OSError, e: 
        sys.stderr.write("daemonize fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
        sys.exit(1) 

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    si = file(stdin, 'r')
    so = file(stdout, 'a+')
    se = file(stderr, 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    
    return str(os.getpid())

def start(pidfile):
    # Check for a pidfile to see if the daemon already runs
    try:
        pf = file(pidfile,'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None

    if pid:
        sys.stderr.write("Minister is already running as process %d, " \
                         "indicated by pidfile %s, --stop first or " \
                         "--restart.\n" % (pid, pidfile))
        sys.exit(1)
    
    pid = daemonize()
    
    # write pidfile
    atexit.register(get_pid_deleter(pidfile))
    file(pidfile,'w+').write("%s\n" % pid)
    
    return pid


def stop(pidfile):
    # Get the pid from the pidfile
    try:
        pf = file(pidfile, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None

    if not pid:
        sys.stderr.write("Minister is not currently running, or cannot find "\
                         "the pidfile: %s\n" % (pidfile))
        return False
    
    try:
        os.kill(pid, signal.SIGTERM)
        while 1:
            eventlet.sleep(1)
            os.kill(pid, signal.SIGKILL)
    except OSError, e:
        err = str(e)
        if err.find("No such process") > 0:
            if os.path.exists(pidfile):
                os.remove(pidfile)
            return True
        else:
            raise e

def get_pid_deleter(pidfile):
    def func():
        if os.path.exists(pidfile):
            os.remove(pidfile)
    return func
