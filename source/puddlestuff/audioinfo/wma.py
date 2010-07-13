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
from mutagen.asf import ASF
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

    _hash = {PATH: 'filepath',
             FILENAME:'filename',
             EXTENSION: 'ext',
             DIRPATH: 'dirpath'}

    format = "Windows Media Audio"

    __translate = {
        "WM/AlbumTitle": "album",
        "Title": "title",
        "Author": "artist",
        "WM/AlbumArtist": "albumartist",
        "WM/Composer": "composer",
        "WM/Writer": "lyricist",
        "WM/Conductor": "conductor",
        "WM/ModifiedBy": "remixer",
        "WM/Producer": "producer",
        "WM/ContentGroupDescription": "grouping",
        "WM/SubTitle": "discsubtitle",
        "WM/TrackNumber": "track",
        "WM/PartOfSet": "discnumber",
        "WM/BeatsPerMinute": "bpm",
        "WM/Copyright": "copyright",
        "WM/ISRC": "isrc",
        "WM/Mood": "mood",
        "WM/EncodedBy": "encodedby",
        "MusicBrainz/Track Id": "musicbrainz_trackid",
        "MusicBrainz/Album Id": "musicbrainz_albumid",
        "MusicBrainz/Artist Id": "musicbrainz_artistid",
        "MusicBrainz/Album Artist Id": "musicbrainz_albumartistid",
        "MusicBrainz/TRM Id": "musicbrainz_trmid",
        "MusicIP/PUID": "musicip_puid",
        "WM/Year": "year",
    }
    __rtranslate = dict([(v, k) for k, v in __translate.iteritems()])

    @getdeco
    def __getitem__(self, key):
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
        elif key in FILETAGS:
            setattr(self, self._hash[key], value)
            return

        if key not in INFOTAGS and isempty(value):
            del(self[key])
        elif key in INFOTAGS or isinstance(key, (int, long)):
            self._tags[key] = value
        elif key in self.__rtranslate:
            if isinstance(value, (str, int, long)):
                value = unicode(value)
            if isinstance(value, basestring):
                value = [value]
            self._tags[key] = value

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

        wmainfo = [('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Channels', unicode(info.channels)),
                   ('Length', self.length)]
        return [('File', fileinfo), ('WMA Info', wmainfo)]

    info = property(_info)


    def load(self, mutfile, tags):
        self._mutfile = mutfile
        self.filename = tags[FILENAME]
        self._tags = tags

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""
        
        
        self.images = None
        tags, audio = self._init_info(filename, ASF)
        if audio is None:
            return

        for name, values in audio.tags.items():
            try: name = self.__translate[name]
            except KeyError: continue
            self._tags[name] = "\n".join(map(unicode, values))

        info = audio.info
        self._tags.update({u"__frequency": strfrequency(info.sample_rate),
                    u"__length": strlength(info.length),
                    u"__bitrate": strbitrate(info.bitrate)})
        self._tags.update(tags)
        self._set_attrs(ATTRIBUTES)
        self._mutfile = audio
        self.filetype = 'Windows Media Audio'
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
            newtag[self.__rtranslate[tag]] = value

        toremove = [z for z in audio if z not in newtag]
        for z in toremove:
            del(audio[z])
        audio.update(newtag)
        audio.save()

filetype = (ASF, Tag, 'WMA')
