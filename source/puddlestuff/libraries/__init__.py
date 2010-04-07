from os.path import join, dirname
from os import listdir
from fnmatch import fnmatch
import traceback, os, imp, sys, pdb


dirpath = dirname(__file__)
__all__ = [f[:-3] for f in listdir(dirpath) if fnmatch(f, '*.py') and
            f != '__init__.py']
#modules = []
#for mod in files:
    #try:
        #modules.append(imp.load_source(mod, join(dirpath, mod + '.py')))
    #except ImportError, detail:
        #sys.stderr.write(u'Error loading %s: %s\n' % (mod, unicode(detail)))
        #traceback.print_exc()
