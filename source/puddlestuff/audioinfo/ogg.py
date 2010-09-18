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
    READONLY, isempty, FILETAGS, EXTENSION, DIRPATH,
    getdeco, setdeco, str_filesize)
from copy import copy

ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
              'modified')

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
    def __getitem__(self, key):
        return self._tags[key]

    @setdeco
    def __setitem__(self,key,value):
        if key in READONLY:
            return
        elif key in FILETAGS:
            setattr(self, self._hash[key], value)
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
            del(self[z])
        self.save()

    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Path', self.filepath),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self.filename),
                    ('Modified', self.modified)]

        ogginfo = [('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Channels', unicode(info.channels)),
                   ('Length', self.length)]
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
        tags, audio = self._init_info(filename, OggVorbis)
        if audio is None:
            return

        for z in audio:
            self._tags[z.lower()] = audio.tags[z]

        info = audio.info
        self._tags.update({u"__frequency": strfrequency(info.sample_rate),
                    u"__length": strlength(info.length),
                    u"__bitrate": strbitrate(info.bitrate)})
        self._tags.update(tags)
        self._set_attrs(ATTRIBUTES)
        self._mutfile = audio
        self._originaltags = self._tags.keys()
        self.filetype = 'Ogg Vorbis'
        self._tags['__filetype'] = self.filetype
        return self

    def save(self):
        """Writes the tags in self._tags
        to self.filename if no filename is specified."""
        filepath = self.filepath

        if self._mutfile.tags is None:
            self._mutfile.add_tags()
        if filepath != self._mutfile.filename:
            self._mutfile.filename = filepath
        audio = self._mutfile

        newtag = {}
        for tag, value in usertags(self._tags).items():
            newtag[tag] = value

        toremove = [z for z in audio if z not in newtag]
        for z in toremove:
            del(audio[z])
        audio.update(newtag)
        audio.save()

filetype = (OggVorbis, Tag, 'VorbisComment')
