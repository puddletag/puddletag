# -*- coding: utf-8 -*-
#ogg.py

#Copyright (C) 2008 - 2009 concentricpuddle

#This audio is part of puddletag, a semi-good music tag editor.

#This program is free software; you can redistribute it and/or modify
#it under the ter ms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import util
from mutagen.oggvorbis import OggVorbis
from util import (strlength, strbitrate, strfrequency, usertags, PATH,
                  getfilename, lnglength, getinfo, FILENAME, INFOTAGS,
                  READONLY, isempty)
from copy import copy

def getdeco(func):
    def f(self, key):
        mapping = self.mapping
        if key in mapping:
            return func(self, mapping[key])
        return func(self, key)
    return f

def setdeco(func):
    def f(self, key, value):
        mapping = self.mapping
        if key in mapping:
            func(self, mapping[key], value)
        return func(self, key, value)
    return f


class Tag(util.MockTag):
    """Ogg Tag class.

    All methods, etc., work as with a usual dictionary.

    To use, instantiate with a filename:
    >>>x = Tag('filename.ogg')

    Afterwards, tags can be edited using a dictionary style. .i.e.
    >>>x['track'] = '1'
    >>>x['title'] = ['Some Title']
    >>>x['artist'] = ['Artist1', 'Artist2']

    Multiple tag values are supported and all values are converted to
    lists internally.

    >>>x['track']
    [u'1]"""
    IMAGETAGS = ()
    mapping = {}
    revmapping = {}

    @getdeco
    def __getitem__(self,key):
        """Get the tag value from self._tags. There is a slight
        caveat in that this method will never return a KeyError exception.
        Rather it'll return ''."""

        try:
            return self._tags[key]
        except KeyError:
            #This is a bit of a bother since there will never be a KeyError exception
            #But its needed for the sort method in tagmodel.TagModel, .i.e it fails
            #if a key doesn't exist.
            return ""

    @setdeco
    def __setitem__(self,key,value):
        if key in READONLY:
          return
        if key == FILENAME:
            self.filename = value
            self._tags[FILENAME] = value
            return

        if key not in INFOTAGS and isempty(value):
            del(self[key])
        elif key in INFOTAGS or isinstance(key, (int, long)):
            self._tags[key] = value
        elif (key not in INFOTAGS) and isinstance(value, (basestring, int, long)):
            self._tags[key.lower()] = [unicode(value)]
        else:
            self._tags[key.lower()] = [unicode(z) for z in value]

    def copy(self):
        tag = Tag()
        tag.load(copy(self._mutfile), self._tags.copy())
        return tag

    def delete(self):
        self._mutfile.delete()
        for z in self.usertags:
            del(self._tags[z])
        self.save()

    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Filename', self[FILENAME]),
                    ('Size', unicode(int(self['__size'])/1024) + ' kB'),
                    ('Path', self[PATH]),
                    ('Modified', self['__modified'])]

        ogginfo = [('Bitrate', self['__bitrate']),
                   ('Frequency', self['__frequency']),
                   ('Channels', unicode(info.channels)),
                   ('Length', self['__length'])]
        return [('File', fileinfo), ('Ogg Info', ogginfo)]

    info = property(_info)


    def load(self, mutfile, tags):
        self._mutfile = mutfile
        self.filename = tags[FILENAME]
        self._tags = tags

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""
        self.images = None
        filename = getfilename(filename)
        audio = OggVorbis(filename)
        tags = getinfo(filename)
        self._tags = {}
        if audio is None:
            return

        for z in audio:
            self._tags[z.lower()] = audio.tags[z]

        info = audio.info
        self._tags.update({u"__frequency": strfrequency(info.sample_rate),
                    u"__length": strlength(info.length),
                    u"__bitrate": strbitrate(info.bitrate)})
        self._tags.update(tags)
        self.filename = tags[FILENAME]
        self._mutfile = audio
        self._originaltags = self._tags.keys()
        return self

    def save(self):
        """Writes the tags in self._tags
        to self.filename if no filename is specified."""

        if self.filename != self._mutfile.filename:
            self._mutfile.filename = self.filename
        audio = self._mutfile

        newtag = {}
        for tag, value in usertags(self).items():
            newtag[tag] = value

        toremove = [z for z in audio if z not in newtag]
        for z in toremove:
            del(audio[z])
        audio.update(newtag)
        audio.save()


filetype = (OggVorbis, Tag, 'VorbisComment')