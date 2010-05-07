import sys, pwd, grp, os, atexit, logging
from optparse import OptionParser
from util import fix_unicode_keys, json
from manager import Manager

### Console Scripts ###
def minister():
    parser = get_parser()
    
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.print_usage()
        sys.exit(0)
    
    if options.user:
        address = Manager.listen(address)
        set_process_owner(options.user)
        
    # Path
    path = args[0]
    if not os.path.exists(path):
        os.makedirs(path)
    
    # Handle Daemon Stoppping
    pidfile = os.path.join(path, 'minister.pid')
    if options.stop:
        if daemon.stop(pidfile):
            print "Minister stopped."
            sys.exit(0)
        else:
            sys.exit(1)
    elif options.restart:
        if daemon.stop(pidfile):
            print "Minister stopped."
    
    # Address 
    ip, _, port = options.socket.partition(':')
    if port: port = int(port)
    address = (ip, port)
    
    # Config
    config = get_config( os.path.join(path, 'config.json') )
    config['path'] = path
    
    if options.debug:
        config['debug'] = True
    
    # Logging
    setup_logger(
        echo = options.verbose,
        path = os.path.join(path, 'logs/minister.log')
    )
    
    # Daemon Start
    if options.start or options.restart:
        print "Minister daemon starting..."
        daemon.start(pidfile)
    
    # Start 'er up.
    manager = Manager(**config)
    atexit.register(manager.close)
    manager.serve(address)


### Support ###
def set_process_owner(spec):
    user, _, group = spec.partition(":")
    if user:
        print "Changing to user: %s" % user
        os.setuid(pwd.getpwnam(user).pw_uid)
    if group:
        print "Changing to group: %s" % group
        os.setgid(grp.getgrnam(group).gr_gid)
    return user, group


def get_config(path):
    file = None
    try:
        file = open(path)
        config = fix_unicode_keys( json.load( file ) )
    except IOError, e:
        config = {
            'services': [{'type': 'admin', 'path': '@admin'}],
        }
    finally:
        if file: file.close()
    return config


def setup_logger(level = "INFO",
                 count = 4,
                 bytes = 2**25,       # 32Mb
                 format = "%(asctime)s - %(levelname)s - %(message)s",
                 echo = False,
                 path = None ):
    
    base = os.path.dirname(path)
    if not os.path.isdir(base):
        os.makedirs(base)
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(format)
    
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=bytes, backupCount=count)
    handler.setLevel(getattr( logging, level.upper() ))
    handler.setFormatter(formatter)
    logger.addHandler( handler )
    
    if not echo:
        echo = "WARNING"
    handler = logging.StreamHandler()
    if isinstance(echo, basestring):
        handler.setLevel(getattr( logging, echo.upper() ))
    else:
        handler.setLevel(getattr( logging, level.upper() ))
    handler.setFormatter(formatter)
    logger.addHandler( handler )

    return logger


def get_parser():
    parser = OptionParser(usage="usage: %prog path-to-repository")
    
    default_user = None
    
    if os.geteuid() == 0:
        default_port = "0.0.0.0:80"
        if 'SUDO_USER' in os.environ:
            default_user = os.environ['SUDO_USER']
    else:
        default_port = "127.0.0.1:8000"
    
    parser.add_option('-s', '--socket',
                        dest="socket",
                        help="Listen on the given SOCKET, defaults to '127.0.0.1:8000' or '0.0.0.0:80' if run as root.",
                        metavar="SOCKET",
                        default=default_port)
    
    parser.add_option("-u", "--user", 
                        dest="user", 
                        help="Run as USER[:GROUP] (defaults to 'minister:minister' if run by root, or if run with sudo the sudoing user)", 
                        metavar="USER", 
                        default=default_user)
                        
    parser.add_option("-v", "--verbose", 
                        action="store_true", dest="verbose",
                        help="Output logging info to stdout.", 
                        default=False)
                        
    parser.add_option("-d", "--debug", 
                        action="store_true", dest="debug",
                        help="Run in debug mode.", 
                        default=False)
                        
    parser.add_option('--start', 
                        dest='start', 
                        action='store_true',
                        help="Start the process as a daemon.")
                        
    parser.add_option('--stop', 
                        dest='stop', 
                        action='store_true',
                        help="Stop the daemon.")
                        
    parser.add_option('--restart', 
                        dest='restart', 
                        action='store_true',
                        help="Restart the process daemon.")

    return parser