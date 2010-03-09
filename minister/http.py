template = """<html><head>
<title>%(title)s</title>
<style>
    body {font-family: Helvetica, Arial, sans-serif; color: #666; margin: 30px}
    h1 {font-size: 24px; margin-top: 0px; }
</style>
</head><body>
<div class="server">minister webserver</div>
<h1>%(title)s</h1>
<p>%(msg)s</p>
</body></html>"""

def render(title, msg=''):
    return (template % {'title': title, 'msg': msg},)

def Http404(environ, start_response, msg="404 Not Found"):
    start_response('404 Not Found', [])
    return render('404 Not Found')
    
def Http304(environ, start_response, headers=[]):
    start_response('304 Not Modified', headers)
    return ("",)

def Http502(environ, start_response):
    start_response('502 Bad Gateway', [])
    return render('502 Bad Gateway', "Name or service not known, bad domain name: %s" % environ['SERVER_NAME'])

def Http405(environ, start_response, allowed=[]):
    start_response('405 Method Not Allowed', [('Allow', " ,".join(allowed))])
    return ("",)

def Http301(environ, start_response, uri):
    start_response('301 Moved Permanently', [('Location', uri)])
    return ("",)

def Http200(environ, start_response, content='', headers=[], type='text/html'):
    headers.append(('Content-Type', type))
    start_response("200 OK", headers)
    if isinstance(content, basestring):
        return (content,)
    return content

HttpResponse = Http200