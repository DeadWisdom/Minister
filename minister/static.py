import os, mimetypes, rfc822, time, eventlet
from urllib import quote
from resource import Resource
from minister import http

class Static(Resource):
    type = 'static'
    allow = ('HEAD', 'GET')
    root = '.'
    default_type = 'text/plain'
    read_block_size = 16 * 4096
    index = ('index.html',)
    strict = True
    exclude = []
    volatile = False            # If True, everything is out of date for modified checking.
    _handlers = {}              # Map extensions to handler functions.
    
    def __call__(self, environ, start_response):
        """Respond to a request when called in the usual WSGI way."""
        if self.allow is not None and environ['REQUEST_METHOD'] not in self.allow:
            return http.MethodNotAllowed(self.allow)(environ, start_response)
        
        requested_path = environ.get('PATH_INFO', '')
        path = self.find_real_path(environ.get('SERVICE_PATH', ''), requested_path)
        
        if not path:
            return self.notfound_or_none(environ, start_response)
        
        for e in self.exclude:
            if path.endswith('/%s' % e):
                return self.notfound_or_none(environ, start_response)
                
        if os.path.isdir(path):
            if requested_path == '' or requested_path.endswith('/'):
                index, path = self.find_index(path)
                if path is None:
                    if not self.strict:
                        return None
                    return self.dir_listing(environ, start_response, path)
                environ['PATH_INFO'] = requested_path + index
            else:
                if not self.strict:
                    return None
                return http.MovedPermanently(self.corrected_dir_uri(environ))(environ, start_response)
        
        try:
            ext = path.rsplit('.', 1)[1]
        except:
            pass
        else:
            if ext in self._handlers:
                response = self._handlers[ext](environ, start_response, path)
                if response:
                    return response
        
        return self.serve(environ, start_response, path)
        
    def notfound_or_none(self, environ, start_response):
        if self.strict:
            return http.NotFound()(environ, start_response)
        else:
            return None

    def find_real_path(self, root, path):
        path = path.split("/")
        root = os.path.abspath(os.path.join( root, self.root ))
        path = os.path.join( root, *path )
        if not path.startswith(root):
            return None
        return path
    
    def serve(self, environ, start_response, path):
        """Serve the file at path."""
        
        if not os.path.exists(path):
            return self.notfound_or_none(environ, start_response)

        try:
            stat = os.stat(path)
            
            if self.volatile:
                modified = time.time()
            else:
                modified = stat.st_mtime
    
            headers = [('Date', rfc822.formatdate(time.time())),
                       ('Last-Modified', rfc822.formatdate(modified)),
                       ('ETag', str(modified))]
            
            if_modified_since = environ.get('HTTP_IF_MODIFIED_SINCE', None)
            if (not self.volatile and if_modified_since):
                parsed = rfc822.parsedate(rfc822.formatdate(modified))
                if parsed >= rfc822.parsedate(if_modified_since):
                    return http.NotModified(headers)(environ, start_response)
            
            if_none_matched = environ.get('HTTP_IF_NONE_MATCH', None)
            if (not self.volatile and if_none_matched):
                if if_none_matched == '*' or if_none_matched == str(modified):
                    return http.NotModified(headers)(environ, start_response)
            
            content_type = mimetypes.guess_type(path)[0] or self.default_type
            headers.append(('Content-Type', content_type))
            headers.append(('Content-Length', str(stat.st_size)))
            start_response("200 OK", headers)
            if environ['REQUEST_METHOD'] == 'GET':
                return environ.get('wsgi.file_wrapper', self.yield_file)(open(path))
            else:
                return ('',)
        except (IOError, OSError), e:
            return http.NotFound()(environ, start_response)
    
    def set_handler(self, ext, func):
        self._handlers[ext] = func
    
    def yield_file(self, file):
        """Yield a file by every *self.read_block_size* bytes."""
        try:
            while True:
                block = file.read(self.read_block_size)
                if not block:
                    break
                yield block
                eventlet.sleep(0)
        finally:
            file.close()
    
    def find_index(self, path):
        """Find an index file in the directory specified at path."""
        for i in self.index:
            candidate = os.path.join(path, i)
            if os.path.isfile(candidate):
                return i, candidate
        return None, None
    
    def dir_listing(self, environ, start_response, path):
        """The client is requesting a directory with no index."""
        return http.NotFound()(environ, start_response)
    
    def corrected_dir_uri(self, environ):
        """Changes the path request to /path/to/directory into /path/to/directory/"""
        url = [environ['wsgi.url_scheme'], '://']

        if environ.get('HTTP_HOST'):
            url.append( environ['HTTP_HOST'] )
        else:
            url.append( environ['SERVER_NAME'] )

            if environ['wsgi.url_scheme'] == 'https':
                if environ['SERVER_PORT'] != '443':
                   url.append(':')
                   url.append(environ['SERVER_PORT'])
            else:
                if environ['SERVER_PORT'] != '80':
                   url.append(':')
                   url.append(environ['SERVER_PORT'])

        url.append( environ.get('SCRIPT_NAME','') )
        url.append( environ.get('PATH_INFO','') )
        url.append( '/' )
        if environ.get('QUERY_STRING'):
            url.append('?')
            url.append(environ['QUERY_STRING'])
        return "".join(url)
