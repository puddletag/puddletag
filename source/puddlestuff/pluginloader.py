import os, traceback, sys
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.plugins import Function
from puddlestuff.constants import FORMATFUNCTIONS, FUNCTIONS, TAGSOURCE
from os.path import splitext

plugindir = os.path.join(PuddleConfig().savedir, u'plugins')
dirpath = os.path.dirname(__file__)

if not dirpath:
    dirpath = '.'
thisfile = __file__

class PuddleFunction:
    pass

def import_py(filename):
    name = splitext(filename)[0]
    module = __import__(name)
    return name, module

def import_dir(dirname):
    module = __import__(dirname)
    return dirname, module

def import_(filename):
    if filename.endswith('.py'):
        return import_py(filename)
    elif os.path.isdir(filename):
        return import_dir(filename)
    else:
        raise Exception(u'%s is not a valid plugin.' % filename)

def get_funcs(module):
    if hasattr(module, 'functions'):
        return module.functions
    functions = []
    for funcname in dir(module):
        func = getattr(module, funcname)
        if callable(func):
            functions.append(func)
        elif isinstance(func, PuddleFunction):
            functions.append(func)
    return functions

def plugin_type(module):
    return module.properties.get('type')

def load_plugs():
    functions = []
    tagsources = []
    join = os.path.join
    for filename in os.listdir(dirpath):
        if (filename == u'__init__.py') or (filename == u'__init__.pyc'):
            continue
        try:
            name, module = import_(filename)
            ptype = plugin_type(module)
            if ptype == FUNCTIONS:
                functions.extend(get_funcs(module))
            elif ptype == TAGSOURCE:
                tagsources.append(module)
        except:
            if filename.endswith('.pyc'):
                continue
            traceback.print_exc()
            continue
    return {FUNCTIONS: functions, TAGSOURCE: tagsources}

plugs = load_plugs()

functions = {}
[functions.update(z) for z in plugs[FUNCTIONS]]
tagsources = plugs[TAGSOURCE]