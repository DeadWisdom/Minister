import os, logging
from eventlet.green import subprocess

__types__ = {}

class SourceMeta(type):
    def __new__(meta, classname, bases, classDict):
        cls = type.__new__(meta, classname, bases, classDict)
        if 'type' in classDict:
            __types__[classDict['type']] = cls
        return cls
    
class Source(object):
    __metaclass__ = SourceMeta
    type = ""
    
    def __init__(self, type=None, src=None):
        self.src = src
        if type:
            self.__class__ = __types__[type]
    
    def check(self, path):
        return False

    def update(self, path):
        return os.path.exists(path)
    
    def command(self, *args):
        logging.info("-" + " ".join(args))
        popen = subprocess.Popen(list(args), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = popen.communicate()
        
        if err:
            logging.error('    ' + '    \n'.join([line for line in err.split('\n')]))
            
        if out:
            logging.error('    ' + '    \n'.join([line for line in out.split('\n')]))
        
        return out or err

class RsyncSource(Source):
    type = "rsync"
    
    def check(self, path):
        path = os.path.abspath( path )
        src = os.path.abspath( self.src )
        if os.path.isdir(src):
            src = src + '/'
        self.command("rsync", '-azr', src, path)
        return False
    
    def update(self, path):
        path = os.path.abspath( path )
        src = os.path.abspath( self.src )
        if os.path.isdir(src):
            src = src + '/'
        return self.command("rsync", '-azr', src, path).find("failed:") == -1


class MercurialSource(Source):
    type = "hg"
    
    def has_hg(self, path):
        return os.path.exists(os.path.join(path, '.hg'))
    
    def check(self, path):
        path = os.path.abspath( path )
        if not self.has_hg(path):
            return True
        return self.command("hg", "incoming", "--repository", path).find('no changes found') == -1
    
    def update(self, path):
        path = os.path.abspath( path )
        if self.has_hg(path):
            return self.command("hg", "pull", "-u", "--repository", path).find('no changes found') == -1
        else:
            return not self.command("hg", "clone", self.src, path).startswith('abort')

class GitSource(Source):
    type = "git"
    
    def has_git(self, path):
        return os.path.exists(os.path.join(path, '.git'))
    
    def check(self, path):
        raise NotImplementedError
        path = os.path.abspath( path )
        if not self.has_hg(path):
            return True
        return self.command("hg", "incoming", "--repository", path).find('no changes found') == -1
    
    def update(self, path):
        path = os.path.abspath( path )
        if self.has_git(path):
            cwd = os.path.abspath('.')
            os.chdir(path)
            response = self.command("git", "pull").find("Already up-to-date") == -1
            os.chdir(cwd)
            return response
        else:
            return self.command("git", "clone", self.src, path)


import urlparse, rfc822
import tarfile, zipfile
from eventlet.green import httplib
from tempfile import TemporaryFile

class HttpSource(Source):
    type = "http"
    
    def get_connection_and_path(self):
        address = urlparse.urlsplit("http:" + self.src)
        con = httplib.HTTPConnection(address.netloc, address.port)
        if address.query:
            return con, address.path + "?" + address.query
        else:
            return con, address.path
    
    def check(self, path):
        con, path = self.get_connection_and_path()
        con.request('HEAD', path)
        response = con.getresponse()
        return rfc822.parsedate(response.getheader('last-modified'))
    
    def tar_members(self, archive):
        """If the tar only has one directory, here we make it instead be that directorie's contents."""
        roots = set(name.partition('/')[0] for name in archive.getnames())
        if len(roots) > 1:
            return
        for member in archive.getmembers():
            member.name = member.name.partition('/')[2]
            if member.name and '..' not in member.name:
                yield member
    
    def zip_members(self, archive):
        roots = set(name.partition('/')[0] for name in archive.namelist())
        if len(roots) > 1:
            return
        for name in archive.namelist():
            name = name.partition('/')[2]
            if name and '..' not in name:
                yield name
    
    def update(self, path):
        filename = urlparse.urlsplit("http:" + self.src).path.rsplit('/', 1)[1]
        tmpfile = self.download(path)
        
        if filename.endswith('.zip'):
            archive = zipfile.ZipFile(file=tmpfile)
            archive.extractall(path=path, members=self.zip_members(archive))
            archive.close()
        else:
            if filename.endswith('.tar.gz')  or filename.endswith('.tgz'):
                mode = 'r:gz'
            elif filename.endswith('.tar.bz2') or filename.endswith('.tbz2'):
                mode = 'r:bz2'
            elif filename.endswith('.tar'):
                mode = 'r'
            else:
                raise RuntimeError("Unknown file type: %r" % tmpfile)
            
            archive = tarfile.open(fileobj=tmpfile, mode=mode)
            try:
                archive.extractall(path=path, members=self.tar_members(archive))
            finally:
                archive.close()
        
        return True
    
    def download(self, path):
        logging.info("Updating source - http:%s", self.src)
        con, path = self.get_connection_and_path()
        con.request('GET', path)
        response = con.getresponse()
        tmpfile = TemporaryFile()
        while True:
            r = response.read(4096)
            if not r: break
            tmpfile.write(r)
        tmpfile.seek(0)
        return tmpfile