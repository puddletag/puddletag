# -*- coding: utf-8 -*-
from util import *

def combine(first, second = None):
    
    class Combined(MockTag):
        mapping = {}
        revmapping = {}
        IMAGETAGS = tuple(set(first.IMAGETAGS).union(second.IMAGETAGS))
        
        def __getattr__(self, val):
            try:
                return getattr(self._first, val)
            except AttributeError:
                if self._second:
                    return getattr(self._second, val)
        
        def __init__(self, filename = None):
            self._first = first(filename)
            if self._second:
                self._second = second(filename)
        
        def _getfilepath(self):
            return self._first.filepath

        def _setfilepath(self,  val):
            self._first.filepath = val
            if self._second:
                self._second.filepath = val

        def _setext(self,  val):
            self._first.ext = val
            if self._second:
                self._second.ext = val

        def _getext(self):
            return self._first.ext

        def _getfilename(self):
            return self._first.filename

        def _setfilename(self, val):
            self._first.filename = val
            self._second.filename = val

        def _getdirpath(self):
            return self._first.dirpath

        def _setdirpath(self, val):
            self._first.dirpath = val
            if self._second:
                self._second.dirpath = val
        
        def _getdirname(self):
            return self._first.dirname
        
        def _setdirname(self, val):
            self._first.dirname = val
            if self._second:
                self._second.dirname = val
        
        filepath = property(_getfilepath, _setfilepath)
        dirpath = property(_getdirpath, _setdirpath)
        dirname = property(_getdirname, _setdirname)
        ext = property(_getext, _setext)
        filename = property(_getfilename, _setfilename)
        
        def _getfiletype(self):
            return self['__filetype']
        
        def _setfiletype(self, val):
            return
        
        filetype = property(_getfiletype, _setfiletype)
        
        def link(self, filename):
            self._first = first.link(self, filename)
            if self._second:
                self._second = second.link(self, filename)
            
            return self._first or self._second
        
        def delete(self):
            self._first.delete()
            if self._second:
                self._second.delete()

        def update(self, dictionary=None, **kwargs):
            self._first.update(dictionary, **kwargs)
            if self._second:
                self._second.update(dictionary, **kwargs)

        def __delitem__(self, key):
            try:
                del(self._first[key])
            except KeyError:
                pass
            
            if self._second:
                try:
                    del(self._second[key])
                except KeyError:
                    pass

        def clear(self):
            self._first.clear()
            if self._second:
                self._second.clear()

        def keys(self):
            if self._second:
                return list(set(self._first.keys()).union(self._second.keys()))
            else:
                return self._first.keys()

        def values(self):
            return [self[key] for key in self]

        def items(self):
            return [(key, self[key]) for key in self]

        tags = property(lambda self: dict(self.items()))

        def __iter__(self):
            return self.keys().__iter__()

        def __contains__(self, key):
            return key in self.keys()

        def __len__(self):
            try:
                return len(self.keys())
            except AttributeError:
                return 0 #This means that that bool(self) = False

        def stringtags(self):
            return stringtags(self)

        def save(self):
            if self._second:
                self._first.update(self._second)
                self._second.update(self._first)
                self._second.save()
            self._first.save()

        def _usertags(self):
            return usertags(self)

        usertags = property(_usertags)

        def get(self, key, default=None):
            return self[key] if key in self else default

        def real(self, key):
            if key in self._first.revmapping:
                return self._first.real(key)
            
            if self._second and key in self._second.revmapping:
                return self._second.real(key)
            return key

        def sget(self, key):
            if key in self:
                return to_string(self[key])
            return u''

        def __getitem__(self, key):
            
            if key == '__image':
                if self._first.IMAGETAGS and self._first.images:
                    return self._first.images
                elif self._second and self._second.IMAGETAGS and self._second.images:
                    return self._second.images
                else:
                    return []
            elif key == '__filetype':
                if self._second:
                    return u'%s, %s'  % (self._first.filetype, 
                        self._second.filetype)
                else:
                    return self._first.filetype

            if key in self._first:
                return self._first[key]
            elif self._second and key in self._second
                return self._second[key]
            else:
                self._first[key]
        
        def __setitem__(self, key, value):
            self._first[key] = value
            if self._second:
                self._second[key] = value
        
        def _get_images(self):
            if self._first.IMAGETAGS and self._first.images:
                return self._first.images
            elif self._second and self._second.IMAGESTAGS:
                return self._second.images
            else:
                return []
        
        def _set_images(self, val):
            if self._first.IMAGETAGS:
                self._first.images = val
            
            if self._second:
                if self._second.IMAGETAGS:
                    self._second.images = val
        
        images = property(_get_images, _set_images)
        
    
    return Combined