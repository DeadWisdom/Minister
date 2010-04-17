import os, logging

get_logger = logging.getLogger

def make_logger(path=None, name=None, level=None, bytes=None, count=None, format=None, echo=None):
    base = os.path.dirname(path)
    if not os.path.isdir(base):
        os.makedirs(base)
    
    logger = logging.getLogger(name)
    logger.setLevel(0)

    formatter = logging.Formatter(format)
    
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=bytes, backupCount=count)
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
    
    logger.options = {
        'path': path,
        'name': name,
        'level': level,
        'bytes': bytes,
        'count': count,
        'format': format,
        'echo': echo
    }
    
    return logger

def dup_logger(existing_name, **override):
    options = get_logger(existing_name).options.copy()
    options.update(override)
    assert name != options['name'], "Must provide a name in your options"
    return make_logger(**options)
    