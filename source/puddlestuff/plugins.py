import os, traceback, imp, sys, shutil
from os import path
from puddlestuff.constants import SAVEDIR, PLUGINDIR

class Function(object):
    def __init__(self, name, function, pprint, args=None, desc=None):
        self.name = name
        self.function = function
        self.func_code = function.func_code
        self.print_string = pprint
        self.desc = desc
        self.args = args

    def __call__(self, *args):
        return self.function(*args)

def load():
    plugmod = path.join(PLUGINDIR, u'__init__.py')
    sys.path.insert(-1, PLUGINDIR)
    if not path.exists(plugmod):
        try:
            os.mkdir(PLUGINDIR)
        except OSError: #Exists already.
            pass
        pluginpath = path.join(path.dirname(__file__), u'pluginloader.py')
        shutil.copy(pluginpath, plugmod)
    return imp.load_source('pluginloader', plugmod)

_loader = load()
functions = _loader.functions
tagsources = _loader.tagsources