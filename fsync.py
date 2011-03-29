#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys, os
import shutil
from urlparse import urlparse
    
try: 
    from hashlib import md5
except ImportError:
    from md5 import md5

try:
    import cPickle as pickle
except:
    import pickle
    
try: 
    import ftputil
    ftputil_FTPHost = ftputil.FTPHost
except ImportError:
    # maybe we are on the remote file walker
    ftputil_FTPHost = object
    pass

# Used for copying file objects; value is 64 KB.
CHUNK_SIZE = 64*1024

class CommonPath:
    def md5file(self, path):
        if self.path.isdir(path):
            return None
    
        # Do md5 check to make sure the file downloaded properly
        checksum = md5()
        f = self.open(path, 'rb')
        # Although the files are small, we can't guarantee the available memory nor that there
        # won't be large files in the future, so read the file in small parts (1kb at time)
        while True:
            part = f.read(CHUNK_SIZE)
            if not part:
                break # end of file        
            checksum.update(part)               
        f.close()            
        # Do we have a match?
        return checksum.hexdigest()

    def walkdir(self, path):
        #print "::walkdir %s" % path
        if path[-1] != self.sep:
            path = "%s%s" % (path, self.sep)
        pathlen = len(path)-1        
        listdir = set(self.listdir(path))

        ret = {'subdirs': {}}
        def set_item(name):
            fullpath = self.path.join(path, name)
            basepath = fullpath[pathlen:].replace("\\", "/")
            if not self.path.isdir(fullpath):
                ret[basepath] = None #self.md5file(fullpath)
            else:
                ret['subdirs']["%s%s" % ("/", name)] = self.walkdir(fullpath)

        map(set_item, listdir)    
        return ret

    def abspath(self, path):
        return "%s%s" % (self.basepath, path)

class FTPPath(ftputil_FTPHost, CommonPath):
    def __init__(self, p, verbose=True):
        username = p.username
        if not username:
            raise Exception("No username provided for domain %s." % p.hostname)
            return
        password = p.password
        if not password:
            raise Exception("No password provided for domain %s." % p.hostname)
            return
        
        if verbose: print "Connecting to %s as %s..." % (p.hostname, username)
        self.verbose = verbose    
        ftputil.FTPHost.__init__(self, p.hostname, username, password)
        self.basepath = p.path
        self.synchronize_times()

    def mtime(self, path):
        """Return the timestamp for the last modification in seconds."""
        # Convert to client time zone (see definition of time
        #  shift in docstring of `FTPHost.set_time_shift`).
        return self.path.getmtime(self.abspath(path)) - self.time_shift()

    def mtime_precision(self, path):
        """Return the precision of the last modification time in seconds."""
        # I think using `stat` instead of `lstat` makes more sense here.
        return self.stat(self.abspath(path))._st_mtime_precision
                
class LocalPath(CommonPath):
    def __init__(self, p, verbose=True):
        self.basepath = os.path.abspath(p)
        self.sep = os.sep
        self.path = os.path
        self.mkdir = os.mkdir
        self.remove = os.remove
        self.rmtree = shutil.rmtree
        self.listdir = os.listdir

    def open(self, path, mode):
        """
        Return a Python file object for file name `path`, opened in
        mode `mode`.
        """
        # This is the built-in `open` function, not `os.open`!
        return open(path, mode)

    def mtime(self, path):
        """Return the timestamp for the last modification in seconds."""
        return os.path.getmtime(self.abspath(path))

    def mtime_precision(self, path):
        """Return the precision of the last modification time in seconds."""
        # Assume modification timestamps for local filesystems are
        #  at least precise up to a second.
        return 1.0
                      
    def close(self):
        pass

class FileSync:
    def __init__(self, source, target, verbose=True):
        self.verbose = verbose
        
        def host_class(path):
            p = urlparse(path)
            if p.scheme == 'ftp':
                return FTPPath(p, verbose=verbose)
            elif os.path.exists(os.path.dirname(path)):
                return LocalPath(path, verbose=verbose)      
            else:
                raise Exception("Unsupported scheme '%s' or invalid path '%s'." % (p.scheme, path))

        self.source = host_class(source)
        self.target = host_class(target)    
        self.actions = None

    def _mkdir(self, target_dir):
        """
        Try to create the target directory `target_dir`. If it already
        exists, don't do anything. If the directory is present but
        it's actually a file, raise a `SyncError`.
        """
        #TODO Handle setting of target mtime according to source mtime
        #  (beware of rootdir anomalies; try to handle them as well).
        #print "Making", target_dir
        if self.target.path.isfile(target_dir):
            raise Exception("target dir '%s' is actually a file" % target_dir)
        if not self.target.path.isdir(target_dir):
            self.target.mkdir(target_dir)
            return True
        return False
            
        
    def compare(self):
        if not self.target.path.isdir(self.target.basepath):
            target_walk = {'subdirs': {}}
        else:
            target_walk = self.target.walkdir(self.target.basepath)
        self.actions = self.dircmp(self.source.walkdir(self.source.basepath), target_walk)
        return self.actions

    def filecmp(self, f):
        return self.source_is_newer_than_target(f) and self.source.md5file(self.source.abspath(f)) != self.target.md5file(self.target.abspath(f))
        #return self.source.md5file(self.source.abspath(f)) != self.target.md5file(self.target.abspath(f))

    def source_is_newer_than_target(self, path):
        """
        Return `True` if the source is newer than the target, else `False`.
       
        Both arguments are `LocalFile` or `RemoteFile` objects.

        For the purpose of this test the source is newer than the
        target, if the target modification datetime plus its precision
        is before the source precision. In other words: If in doubt,
        the file should be transferred.
        """
        return self.source.mtime(path) + self.source.mtime_precision(path) >= \
               self.target.mtime(path)

    @staticmethod
    def get_files_dirs(myset):
        files = set(myset.keys())-set(['subdirs'])
        try:
            dirs = set(myset['subdirs'].keys())
        except KeyError:
            dirs = set()
        return (files, dirs)

    @staticmethod
    def set_compare(set1, set2):
        (files1, dir1) = FileSync.get_files_dirs(set1)
        (files2, dir2) = FileSync.get_files_dirs(set2)
        return (files1 - files2, # newfiles
                files2 - files1, # removedfiles
                files1 & files2, # commonfiles
                dir1 - dir2,     # newdirs
                dir2 - dir1,     # removeddirs
                dir1 & dir2,     # commondirs
                )
   
    def dircmp(self, set1, set2, prepend=''):
        actions = []

        (newfiles, removedfiles, commonfiles, newdirs, removeddirs, commondirs) = FileSync.set_compare(set1, set2)

        def set_action(act, filename, condition=True):
            if condition:
                if self.verbose: print "%s %s%s" % (act, prepend, filename)
                actions.append((act, "%s%s" % (prepend, filename)))

        map(lambda x: set_action("copy", x), newfiles)
        map(lambda x: set_action("remove", x), removedfiles)
        map(lambda x: set_action("copy", x, self.filecmp("%s%s" % (prepend, x))), commonfiles)
        map(lambda x: set_action("mkdir", x), newdirs)
        map(lambda x: set_action("rmtree", x), removeddirs)
       
        for f in (newdirs | commondirs):
            sub1 = set1['subdirs'][f]
            try:
                sub2 = set2['subdirs'][f]
            except:
                sub2 = {}
            actions.extend( self.dircmp(sub1, sub2, "%s%s" % (prepend, f)) )
           
        return actions
      
    def sync(self, callback=None):
        self._mkdir(self.target.basepath)
        for (action, path) in self.actions:
            src = self.source.abspath(path)
            dst = self.target.abspath(path)
            if callback:
                if not callback(action, path):
                    break
            if action == 'copy':
                source = self.source.open(src, "rb")
                try:
                    target = self.target.open(dst, "wb")
                    try:
                        shutil.copyfileobj(source, target, length=CHUNK_SIZE)
                    finally:
                        target.close()
                finally:
                    source.close()               
#                print action, src, "->", dst
            else:
#                print action, dst
                func = getattr(self.target, action)
                func(dst)

    def close(self):
        self.source.close()
        self.target.close()
                        
def main():
    from optparse import OptionParser

    parser = OptionParser(usage="%prog [options] source dest", version="%prog 1.0")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", help='Verbose')    
    (options, args) = parser.parse_args()
    if len(args) <2:
        parser.print_help()
        sys.exit()
    
    fsync = FileSync(*args, verbose=options.verbose)
    fsync.compare()
    fsync.sync()
    fsync.close()

if __name__ == '__main__':
    main()
    
