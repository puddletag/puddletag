# -*- coding: utf-8 -*-
from util import *
from puddlestuff.audioinfo import TAG_TYPES

def combine(first, *others):
    
    class Multi(MockTag):
        mapping = {}
        revmapping = {}
        IMAGETAGS = first.IMAGETAGS
        
        def __init__(self, filename = None):
            self._first = first(filename)
            self._others = [tag(filename) for tag in others]
            self._others = [z for z in self._others if z is not None]
            self._filetypes = {}

        def _getdirname(self):
            return self._first.dirname
        
        def _setdirname(self, val):
            self._first.dirname = val
            self._set_attr('dirname', val)

        def _getdirpath(self):
            return self._first.dirpath

        def _setdirpath(self, val):
            self._first.dirpath = val
            self._set_attr('dirpath', val)

        def _getext(self):
            return self._first.ext

        def _setext(self,  val):
            self._first.ext = val
            self._set_attr('ext', val)
        
        def _get_images(self):
            if self._first.IMAGETAGS and self._first.images:
                return self._first.images
            elif self._others:
                for tag in self._others:
                    if tag.IMAGETAGS and tag.images:
                        return tag.images
            return []
        
        def _set_images(self, val):
            if self._first.IMAGETAGS:
                self._first.images = val
            
            if self._others:
                for tag in self._others:
                    if tag.IMAGETAGS:
                        tag.images = val
        
        def _info(self):
            info = self._first.info
            [info.extend(z.info) for z in self._others]
            return info

        def _getfilename(self):
            return self._first.filename

        def _setfilename(self, val):
            self._first.filename = val
            self._set_attr('filename', val)

        def _getfilepath(self):
            return self._first.filepath

        def _setfilepath(self,  val):
            self._first.filepath = val
            self._set_attr('filepath', val)

        def _getfiletype(self):
            return self['__filetype']
        
        def _setfiletype(self, val):
            return
        
        def _usertags(self):
            return usertags(self)

        dirname = property(_getdirname, _setdirname)
        dirpath = property(_getdirpath, _setdirpath)
        ext = property(_getext, _setext)
        filename = property(_getfilename, _setfilename)
        filepath = property(_getfilepath, _setfilepath)
        filetype = property(_getfiletype, _setfiletype)
        images = property(_get_images, _set_images)
        info = property(_info)
        tags = property(lambda self: dict(self.items()))
        usertags = property(_usertags)
    
        def add_tag(self, filetype, tag):
            self._others.append(tag)
            self._filetypes[filetype] = tag
        
        def clear(self):
            self._first.clear()
            self._set(lambda z: z.clear())

        def __contains__(self, key):
            return key in self.keys()

        def delete(self, tag=None):
            if tag is None:
                self._first.delete()
                self._set(lambda z: z.delete())
            else:
                if tag in self._filetypes:
                    audio = self._filetypes[tag]
                    audio.delete()
                    del(self._filetypes[tag])
                    self._others.remove(audio)

        def __delitem__(self, key):
            try:
                del(self._first[key])
            except KeyError:
                pass
            
            for tag in self._others:
                try:
                    del(tag[key])
                except KeyError:
                    pass

        def __getattr__(self, val):
            try:
                return getattr(self._first, val)
            except AttributeError, e:
                for tag in self._others:
                    try:
                        return getattr(tag, val)
                    except AttributeError:
                        pass
                raise e

        def __getitem__(self, key):
            if key == '__image':
                return self.images
            elif key == '__filetype':
                if self._others:
                    return u'%s, %s'  % (self._first.filetype, 
                        u', '.join([z.filetype for z in self._others]))
                else:
                    try:
                        return self._first.filetype
                    except:
                        pdb.set_trace()
                        return self._first.filetype

            if key in self._first:
                return self._first[key]
            elif self._others:
                for tag in self._others:
                    if key in tag:
                        return tag[key]

            return self._first[key]

        def get(self, key, default=None):
            return self[key] if key in self else default

        def items(self):
            return [(key, self[key]) for key in self]

        def __iter__(self):
            return self.keys().__iter__()

        def keys(self):
            if self._others:
                keys = set(self._first.keys())
                for tag in self._others:
                    keys = keys.union(tag.keys())
                return list(keys)
            else:
                return self._first.keys()

        def __len__(self):
            try:
                return len(self.keys())
            except AttributeError:
                return 0 #This means that that bool(self) = False
        
        def link(self, filename):
            self._first = first.link(self, filename)
            for tag in others:
                self._others = filter(None, 
                    [tag.link(self, filename) for tag in others])
            return self._first or self._others[0]

        def real(self, key):
            if key in self._first.revmapping:
                return self._first.real(key)
            return key
        
        def remove(self, filetype):
            c = TAG_TYPES[filetype]
            if isinstance(self._first, c):
                self._first.delete()
            if filetype in self._filetypes:
                tag = self._filetypes[filetype]
                self._others.remove(tag)
                del(self._filetypes[filetype])

        def save(self):
            if self._others:
                tags = {}
                [tags.update(tag.usertags) for tag in self._others]
                tags.update(self._first.usertags)
                [tag.update(tags) for tag in self._others]
                [tag.save() for tag in self._others]
            self._first.save()

        def sget(self, key):
            if key in self:
                return to_string(self[key])
            return u''

        def _set(self, func):
            map(func, self._others)

        def _set_attr(self, attr, val):
            [setattr(tag, attr, val) for tag in self._others]

        def __setitem__(self, key, value):
            self._first[key] = value
            self._set(lambda z: z.__setitem__(key, value))
        
        def stringtags(self):
            return stringtags(self)
        
        def update(self, dictionary=None, **kwargs):
            self._first.update(dictionary, **kwargs)
            self._set(lambda z: z.update(dictionary, **kwargs))
        
        def values(self):
            return [self[key] for key in self]

    return Multi