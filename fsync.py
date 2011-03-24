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

def md5file(path):
    if os.path.isdir(path):
        return None
    
    # Do md5 check to make sure the file downloaded properly
    checksum = md5()
    f = file(path, 'rb')
    # Although the files are small, we can't guarantee the available memory nor that there
    # won't be large files in the future, so read the file in small parts (1kb at time)
    while True:
        part = f.read(1024)
        if not part:
            break # end of file        
        checksum.update(part)               
    f.close()            
    # Do we have a match?
    return checksum.hexdigest()

def walkdir(path):
    #print "::walkdir %s" % path
    if path[-1] != os.sep:
        path = "%s%s" % (path, os.sep)
    pathlen = len(path)-1        
    listdir = set(os.listdir(path))

    ret = {'subdirs': {}}
    def set_item(name):
        fullpath = os.path.join(path, name)
        basepath = fullpath[pathlen:].replace("\\", "/")
        if not os.path.isdir(fullpath):
            ret[basepath] = md5file(fullpath)
        else:
            ret['subdirs']["%s%s" % ("/", name)] = walkdir(fullpath)

    map(set_item, listdir)    
    return ret
    
def dircmp(set1, set2, prepend='', verbose=False):
    files1 = set(set1.keys())-set(['subdirs'])
    files2 = set(set2.keys())-set(['subdirs'])
    actions = []
    
    if set1.has_key('subdirs'):
        dir1 = set(set1['subdirs'].keys())
    else:
        dir1 = set()

    if set2.has_key('subdirs'):
        dir2 = set(set2['subdirs'].keys())
    else:
        dir2 = set()

    if files1 - files2:
#        print "files only in 1:"
        for f in files1 - files2:
            if verbose: print "+ %s%s" % (prepend, f)
            actions.append(("copy", "%s%s" % (prepend, f)))
    if files2 - files1:
#        print "files only in 2:"
        for f in files2 - files1:
            if verbose: print "- %s%s" % (prepend, f)
            actions.append(("remove", "%s%s" % (prepend, f)))            

    if files2 & files1:
#        print "files in common:"
        for f in files1 & files2:
            if set1[f] == set2[f]:
#                print "= %s%s" % (prepend, f)       
                pass
            else:
                if verbose: print "M %s%s" % (prepend, f)
                actions.append(("copy", "%s%s" % (prepend, f)))

    if dir1 - dir2:
#        print "Sub only in 1:"
        for f in dir1 - dir2:
            if verbose: print "D+ %s%s" % (prepend, f)
            actions.append(("mkdir", "%s%s" % (prepend, f)))
            actions.extend( dircmp(set1['subdirs'][f], {}, "%s%s" % (prepend, f)) )

    if dir2 - dir1:
#        print "Sub only in 2:"
        for f in dir2 - dir1:
            if verbose: print "D- %s%s" % (prepend, f)
            actions.append(("rmtree", "%s%s" % (prepend, f)))            

    if dir1 & dir2:
#        print "Sub in common:"
        for f in dir1 & dir2:
#            print "%s/%s" % (prepend, f)
            actions.extend(dircmp(set1['subdirs'][f], set2['subdirs'][f], "%s%s" % (prepend, f)))
    return actions

class FTPPath(ftputil_FTPHost):
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

    def abspath(self, path):
        return "%s%s" % (self.basepath, path)
                
    def walkdir(self):
        return remote_walkdir(self.basepath)

class LocalPath:
    def __init__(self, p, verbose=True):
#        if not os.path.isdir(p.path):
#            raise Exception("Invalid local path '%s'." % p.path)
#            return
        self.basepath = os.path.abspath(p)
        self.path = os.path
        self.mkdir = os.mkdir
        self.remove = os.remove
        self.rmtree = shutil.rmtree

    def open(self, path, mode):
        """
        Return a Python file object for file name `path`, opened in
        mode `mode`.
        """
        # This is the built-in `open` function, not `os.open`!
        return open(path, mode)
      
    def walkdir(self):
        return walkdir(self.basepath)        

    def abspath(self, path):
        return "%s%s" % (self.basepath, path)
                
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
            target_walk = self.target.walkdir()
        self.actions = dircmp(self.source.walkdir(), target_walk, verbose=self.verbose)
        return self.actions

    def sync(self):
        self._mkdir(self.target.basepath)
        for (action, path) in self.actions:
            src = self.source.abspath(path)
            dst = self.target.abspath(path)
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
##                if isinstance(self.source, LocalPath) and isinstance(self.target, LocalPath):
##                    shutil.copyfile(src, dst)
##                elif isinstance(self.source, LocalPath) and isinstance(self.target, FTPPath):
##                    # upload
##                    self.target.upload(src, dst, mode='b')
##                elif isinstance(self.source, FTPPath) and isinstance(self.target, LocalPath):
##                    # download
##                    self.source.download(src, dst, mode='b')
##                elif isinstance(self.source, FTPPath) and isinstance(self.target, FTPPath):
##                    # ????
##                    source = self.source.file(src, 'rb')
##                    target = self.target.file(dst, 'wb')
##                    self.target.host.copyfileobj(source, target)
##                    source.close()
##                    target.close()
                print action, src, "->", dst
            else:
                print action, dst
                func = getattr(self.target, action)
                func(dst)

    def close(self):
        self.source.close()
        self.target.close()
                        
def main():
    from optparse import OptionParser

    parser = OptionParser(usage="%prog [options] source dest", version="%prog 1.0")
    parser.add_option('-u', '--user', dest='username', help='ftp username')
    parser.add_option('-p', '--pass', dest="password", help='ftp password')
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", help='Verbose')    
    (options, args) = parser.parse_args()
    if len(args) <2:
        parser.print_help()
        sys.exit()
    
    fsync = FileSync(*args, verbose=options.verbose)
    fsync.compare()
    fsync.sync()
    fsync.close()
    
    sys.exit()
    
    stat = [None, None]
    islocal = [True, True]
    paths = [None, None]
    host = [None, None]
    for i in xrange(len(args)):
        (scheme, netloc, path, params, q, f) = urlparse(args[i])
        if scheme == 'ftp':
            import ftputil
            if options.verbose: print "Connecting to %s, u %s p %s..." % (netloc, options.user, options.password)
            host[i] = ftputil.FTPHost(netloc, options.user, options.password)
            #if not host[i].path.isdir(path):
            #    print "Invalid remote path '%s'." % path
            paths[i] = path
            stat[i] = remote_walkdir(path)
            islocal[i] = False
        elif scheme == '':
            if not os.path.isdir(path):
                print "Invalid local path '%s'." % path
                sys.exit()
            paths[i] = os.path.abspath(path)
            stat[i] = walkdir(path)
        else:
            print "Unsupported scheme '%s'." % scheme
            sys.exit()
    
    for (action, path) in dircmp(*stat, verbose=options.verbose):
        src = "%s%s" % (paths[0], path)
        dst = "%s%s" % (paths[1], path)
        if action == 'copy':
            if islocal[0] and islocal[1]:
                # local copy
                shutil.copyfile(src, dst)
            elif islocal[0] and not islocal[1]:
                # upload
                host[1].upload(src, dst)
            elif islocal[1] and not islocal[0]:
                # download
                host[0].download(src, dst)
            else:
                # ????
                source = host[0].file(src, 'r')
                target = host[1].file(dst, 'w')
                host[1].copyfileobj(source, target)
                source.close()
                target.close()
            print action, src, "->", dst
            
        elif action == 'remove':
            if islocal[1]:
                # local copy
                os.remove(dst)
            elif not islocal[1]:
                # upload
                host[1].remove(dst)
            print action, dst

        elif action == 'mkdir':
            if islocal[1]:
                # local copy
                os.mkdir(dst)
            elif not islocal[1]:
                # upload
                host[1].mkdir(dst)
            print action, dst
            
        elif action == 'rmtree':
            if islocal[1]:
                # local copy
                shutil.rmtree(dst)
            elif not islocal[1]:
                # upload
                host[1].rmtree(dst)
            print action, dst

def remote_walkdir(path):
    import urllib2
    
    f = urllib2.urlopen("http://www.terranovanet.it/cgi-bin/remotefsync.py?%s" % path)
    data = pickle.load(f)
    f.close()
    return data
    
def process_remote_dir():
    curdir = os.environ.get('DOCUMENT_ROOT', "..")
    
    print "Content-Type: text/plain"
    print "Cache-Control: no-store, no-cache, must-revalidate"
    print "Pragma: no-cache\n"
    path = os.environ['QUERY_STRING']
    if path[0] == os.sep:
        path = path[1:]
        
    path = os.path.join(curdir, path)
    path = os.path.normpath(path)
    if os.path.isdir(path):
        print pickle.dumps(walkdir(path))

if __name__ == '__main__':
    if os.environ.has_key('QUERY_STRING'):
        process_remote_dir()
    else:
        main()
    
