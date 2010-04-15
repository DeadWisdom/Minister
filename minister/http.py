from util import simple_template

template = """<html><head>
<title>{{title}}</title>
<style>
    body {font-family: Helvetica, Arial, sans-serif; color: #666; margin: 30px}
    h1 {font-size: 32px; margin-top: 0px; }
</style>
</head><body>
<div class="server">minister webserver</div>
<h1>{{title}}</h1>
<p>{{msg}}</p>
</body></html>"""

def render(title, msg=''):
    return simple_template(template, {'title': title, 'msg': msg})

def Response(content='', headers=None, type='text/html', status="200 OK"):
    headers = headers or [('Content-Type', type)]
    def app(environ, start_response):
        start_response(status, headers)
        if isinstance(content, basestring):
            return (content,)
        return content
    return app
    
def MovedPermanently(uri, headers=[]):
    return Response(status='301 Moved Permanently', headers=headers + [('Location', uri)])

def NotModified(headers=[]):
    return Response(status='304 Not Modified', headers=headers)

def NotFound(content=render("404 Not Found")):
    return Response(status='404 Not Found', content=content)

def MethodNotAllowed(allowed=[]):
    return Response(status='405 Method Not Allowed', headers=[('Allow', " ,".join(allowed))])

def InternalServerError(content=render("500 Internal Server Error")):
    return Response(status="500 Internal Server Error", content=content)

def BadGateway(content=render('502 Bad Gateway', "Name or service not known, bad domain name.")):
    return Response(status="502", content=content)