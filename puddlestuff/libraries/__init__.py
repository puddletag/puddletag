from fnmatch import fnmatch
from os import listdir
from os.path import dirname

dirpath = dirname(__file__)
__all__ = [f[:-3] for f in listdir(dirpath) if fnmatch(f, '*.py') and
           f != '__init__.py']
