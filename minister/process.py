import os, sys, signal, time, logging

import eventlet
from eventlet.green import subprocess

class Process(object):
    """
    A wrapper around subprocess.Popen, but keeps track of the process, and
    allows you to check its status, rerun the process, and figure out if it
    has failed, meaning it has restarted 3 times in the past 30 seconds.
    """
    def __init__(self, path=None, executable=None, args=[], env={}):
        self.pid = None
        self.path = os.path.abspath( path )
        self.executable = executable
        self.args = [executable] + args
        self.env = env
        self.returncode = None
        
        self._process = None
        self._starts = []   # We keep track of start times, so that we can
                            # tell how many times we restarted.
    
    def readloop(self):
        def outloop():
            while True:
                if not self._process:
                    return
                line = self._process.stdout.readline()
                if not line:
                    return
                logging.info("- %s", line[:-1])
        def errloop():
            while True:
                if not self._process:
                    return
                line = self._process.stderr.readline()
                if not line:
                    return
                logging.error("- %s", line[:-1])
        eventlet.spawn_n(outloop)
        eventlet.spawn_n(errloop)
    
    def run(self):
        """Run the process."""
        self._starts.append(time.clock())
        self._starts = self._starts[-3:]
        
        try:
            self._process = subprocess.Popen(
                                self.args,
                                executable = self.executable,
                                stdout = subprocess.PIPE,
                                stderr = subprocess.PIPE,
                                shell = False,
                                cwd = self.path,
                                env = self.env)
        except OSError, e:
            logging.error("%s - %s", " ".join(self.args), e)
            return False
            
        self.readloop()
        return True
        
    def check(self):
        """
        Returns True if the process is running.  When it fails, the returncode
        will be available as the ``returncode`` attribute.
        """
        if (not self._process):
            return False
        if self._process.poll():
            self.returncode = self._process.returncode
            self._process = None
            return False
        return True
    
    def is_failure(self, leeway=30):
        """
        Return true if the process has started three times in the last 
        ``leeway`` seconds.
        """
        if len(self._starts) < 3:
            return False
        else:
            #It's a failure if the third to last run was less than <leeway> seconds ago.
            return (time.clock() - self._starts[-3]) < leeway
    
    def terminate(self):
        """
        Terminate the process, sends SIGTERM.  On windows this is the same
        as kill().
        """
        if self._process:
            if hasattr(self._process, 'terminate'): # python >= 2.6
                self._process.terminate()
            elif sys.platform.startswith('win'):    # Windows, python <= 2.5
                import win32process
                return win32process.TerminateProcess(self._process._handle, -1)
            else:                                   # Posix, python <= 2.5
                os.kill(self._process.pid, signal.SIGTERM)
    
    def kill(self):
        """
        Kills the process, sends SIGKILL.  On windows this is the same
        as terminate().
        """
        if self._process:
            if hasattr(self._process, 'kill'):      # python >= 2.6
                self._process.kill()
            elif sys.platform.startswith('win'):    # Windows, python <= 2.5
                import win32process
                return win32process.TerminateProcess(self._process._handle, -1)
            else:                                   # Posix, python <= 2.5
                os.kill(self._process.pid, signal.SIGKILL)