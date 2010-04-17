import logging

def make_logger(path=None, name=None, level=None, max_bytes=None, count=None, format=None, echo=None):
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
    
logging = logging.getLogger("minister")