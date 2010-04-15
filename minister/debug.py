import traceback, os, re
from util import simple_template, error_info

import logging
logger = logging.getLogger('minister')

template_base = """<html><head>
<title>{{title}}</title>
<style>
    body {font-family: Helvetica, Arial, sans-serif; color: #666; margin: 30px}
    h1 {font-size: 32px; margin-top: 0px; margin-bottom: 0px}
    a { color: #499D59; text-decoration: none }
    a:hover { text-decoration: underline }
    .list { font-size: 14px; margin-top: 12px; }
    .list .frame { margin-bottom: 2px }
    .list .frame pre { margin: 4px 16px 12px; padding: 0; color: #499D59 }
    .list .filename { display: none }
    .list .short { display: inline }
    .list .url { margin: 4px 10px; }
    .byline { font-size: 14px; margin: 50px 0px 15px}
</style>
</head><body>
<div class="server">minister webserver</div>
<h1>{{title}}</h1>
<div class='byline'>{{byline}}</div>
<div class='list'>
    {{list}}
</div>
</body></html>"""

url_template = """<div class='url'><a href="{{site}}/{{url}}">{{site}}/{{url}}</a></div>"""

def DebugNotFound(manager):
    def app(environ, start_response):
        urls = []
        if manager.address[1] != '80':
            port = ":%s" % manager.address[1]
        else:
            port = ""
        
        for resource in manager.layout.resources:
            if resource.site:
                site = "http://" + resource.site + port
            else:
                site = ""
            urls.append( simple_template(url_template, {'url': resource.url, 'site': site}) )
    
        for resource in manager.services.resources:
            if resource.status not in ("active", "struggling"):
                continue
            if resource._service.disabled or resource.disabled:
                continue
            
            url = resource._service.url
            if url is None:
                continue
        
            if resource._service.site not in ('*', None):
                site = "http://" + resource._service.site + port
            else:
                site = ""
            urls.append( simple_template(url_template, {'url': url, 'site': site}) )
    
        start_response('404 Not Found', [])
        return simple_template(template_base, {
            'title': '404 Not Found',
            'list': "\n".join(urls),
            'byline': 'Available Resources'
        })
    return app


traceback_template = """<div class='frame'>
    <div class='short'>{{short}}</div><div class='filename'>{{filename}}</div> &mdash; line {{lineno}}
    <pre>{{src}}</pre>"""

def DebugInternalServerError(exception):
    def app(environ, start_response):
        exc_type, exc_value, tb = exception
        start_response('500 Internal Server Error', [])
        return simple_template(template_base, {
            'title': '500 Internal Server Error',
            'list': "\n".join(get_frames(tb)),
            'byline': "%s: %s" % (exc_type.__name__, exc_value)
        })
    return app

def get_frames(tb):
    frames = []
    while tb is not None:
        if tb.tb_frame.f_locals.get('__traceback_hide__'):
            tb = tb.tb_next
            continue
        filename = tb.tb_frame.f_code.co_filename
        function = tb.tb_frame.f_code.co_name
        lineno = tb.tb_lineno - 1
        module_name = tb.tb_frame.f_globals.get('__name__')
        short = os.path.join( os.path.basename(os.path.dirname(filename)), os.path.basename(filename) )
        pre, src, post = read_file(filename, lineno, 11)
        frames.append(simple_template(traceback_template, {
            'filename': filename,
            'short': short,
            'lineno': str(lineno),
            'function': function,
            'src': src.strip()
        }))
        tb = tb.tb_next
    return frames

def read_file(filename, lineno, context_lines):
    source = []
    
    try:
        f = open(filename)
        try:
            source = f.readlines()
        finally:
            f.close()
    except (OSError, IOError):
        pass

    encoding = 'ascii'
    for line in source[:2]:
        # File coding may be specified. Match pattern from PEP-263
        # (http://www.python.org/dev/peps/pep-0263/)
        match = re.search(r'coding[:=]\s*([-\w.]+)', line)
        if match:
            encoding = match.group(1)
            break
    source = [unicode(sline, encoding, 'replace') for sline in source]

    lower_bound = max(0, lineno - context_lines)
    upper_bound = lineno + context_lines

    pre_context = [line.strip('\n') for line in source[lower_bound:lineno]]
    context_line = source[lineno].strip('\n')
    post_context = [line.strip('\n') for line in source[lineno+1:upper_bound]]

    return pre_context, context_line, post_context