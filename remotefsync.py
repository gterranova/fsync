#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys, os
import cgitb; cgitb.enable()

try: 
    from hashlib import md5
except ImportError:
    from md5 import md5

try:
    import cPickle as pickle
except:
    import pickle
    
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
    
def process_remote_dir():
    curdir = os.environ.get('DOCUMENT_ROOT', "..")
    sys.path.append(os.path.join(curdir,'cgi-bin','site_packages'))
    import simplejson as json
    
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
    try:
        process_remote_dir()
    except Exception, e:
        print "Content-Type: text/plain\n"
        print "Error occurred", e
#    print "Content-type: text/plain"
#    print "Cache-Control: no-store, no-cache, must-revalidate"
#    print "Pragma: no-cache\n"
#    print "cucu"

