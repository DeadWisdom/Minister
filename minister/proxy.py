"""
Torn from Ian Bicking's WSGIProxy (http://bitbucket.org/ianb/wsgiproxy/)

As this constitutes a "substantial portion", WSGIProxy Contains the following notice:
# (c) 2005 Ian Bicking and contributors; written for Paste (http://pythonpaste.org)
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""

import eventlet, socket
from resource import Resource
from http import Http502
#import http as httplib
from eventlet.green import httplib
from urllib import quote as url_quote

# Remove these headers from response (specify lower case header
# names):
filtered_headers = (
    'transfer-encoding',
)

class Proxy(Resource):
    type = 'proxy'
    address = ('', 0)
    
    def __call__(self, environ, start_response):
        """
        HTTP proxying WSGI application that proxies the exact request
        given in the environment.  All controls are passed through the
        environment.

        This connects to the server given in SERVER_NAME:SERVER_PORT, and
        sends the Host header in HTTP_HOST -- they do not have to match.

        Does not add X-Forwarded-For or other standard headers
        """
        scheme = environ['wsgi.url_scheme']
        if scheme == 'http':
            ConnClass = httplib.HTTPConnection
        elif scheme == 'https':
            ConnClass = httplib.HTTPSConnection
        else:
            raise ValueError("Unknown scheme: %r" % scheme)
        
        conn = ConnClass(*self.address)
        headers = {}
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                key = key[5:].replace('_', '-').title()
                headers[key] = value
        path = (url_quote(environ.get('SCRIPT_NAME', ''))
                + url_quote(environ.get('PATH_INFO', '')))
        if environ.get('QUERY_STRING'):
            path += '?' + environ['QUERY_STRING']
        try:
            content_length = int(environ.get('CONTENT_LENGTH', '0'))
        except ValueError:
            content_length = 0
        if content_length:
            body = environ['wsgi.input'].read(content_length)
        else:
            body = ''
        headers['Content-Length'] = content_length
        if environ.get('CONTENT_TYPE'):
            headers['Content-Type'] = environ['CONTENT_TYPE']
        if not path.startswith("/"):
            path = "/" + path
        try:
            conn.request(environ['REQUEST_METHOD'], path, body, headers)
        except socket.error, exc:
            if exc.args[0] == -2:
                return Http502(environ, start_response)
            raise
        res = conn.getresponse()
        headers_out = parse_headers(res.msg)
        status = '%s %s' % (res.status, res.reason)
        start_response(status, headers_out)
        length = res.getheader('content-length')
        if length is not None:
            body = [ res.read(int(length)) ]
        else:
            body = [ res.read() ]
        conn.close()
        return body

def parse_headers(message):
    """
    Turn a Message object into a list of WSGI-style headers.
    """
    headers_out = []
    for full_header in message.headers:
        if not full_header:
            # Shouldn't happen, but we'll just ignore
            continue
        if full_header[0].isspace():
            # Continuation line, add to the last header
            if not headers_out:
                raise ValueError("First header starts with a space (%r)" % full_header)
            last_header, last_value = headers_out.pop()
            value = last_value + ', ' + full_header.strip()
            headers_out.append((last_header, value))
            continue
        try:
            header, value = full_header.split(':', 1)
        except:
            raise ValueError("Invalid header: %r" % full_header)
        value = value.strip()
        if header.lower() not in filtered_headers:
            headers_out.append((header, value))
    return headers_out
