def Http404(environ, start_response, msg="404 Not Found"):
    start_response('404 Not Found', [])
    return (msg,)
    
def Http304(environ, start_response, headers=[]):
    start_response('304 Not Modified', headers)
    return ("",)

def Http502(environ, start_response):
    start_response('502 Bad Gateway', [])
    return ("Name or service not known, bad domain name: ", environ['SERVER_NAME'])

def Http405(environ, start_response, allowed=[]):
    start_response('405 Method Not Allowed', [('Allow', " ,".join(allowed))])
    return ('',)

def Http301(environ, start_response, uri):
    start_response('301 Moved Permanently', [('Location', uri)])
    return ("",)

HttpRedirect = Http301

def Http200(environ, start_response, content='', headers=[], type='text/html'):
    headers.append(('Content-Type', type))
    start_response("200 OK", headers)
    if isinstance(content, basestring):
        return (content,)
    return content

HttpResponse = Http200