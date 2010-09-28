# -*- coding: utf-8 -*-
#apev2.py

#Copyright (C) 2008-2009 concentricpuddle

#This audio is part of puddletag, a semi-good music tag editor.

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from mutagen.apev2 import APEv2File

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
    getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY, DIRNAME,
    FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created',
    'modified', 'filetype')

def get_class(mutagen_file, base_function, attrib_fields):
    class Tag(util.MockTag):
        """Tag class for APEv2 files.

        Tags are used as in ogg.py"""
        IMAGETAGS = ()
        mapping = {}
        revmapping = {}
        _hash = {PATH: 'filepath',
            FILENAME:'filename',
            EXTENSION: 'ext',
            DIRPATH: 'dirpath',
            DIRNAME: 'dirname'}

        @getdeco
        def __getitem__(self,key):
            return self._tags[key]

        @setdeco
        def __setitem__(self, key, value):
            
            if key == '__image':
                return

            if isinstance(key, (int, long)):
                self._tags[key] = value
                return
            elif key in READONLY:
                return
            elif key in FILETAGS:
                setattr(self, self._hash[key], value)
                return
            elif key in INFOTAGS:
                self._tags[key] = value
                return
            elif key not in INFOTAGS and isempty(value):
                del(self[key])
                return


            if (key not in INFOTAGS) and isinstance(value, (basestring, int, long)):
                self._tags[key] = [unicode(value)]
            else:
                self._tags[key] = [unicode(z) for z in value]

        def copy(self):
            tag = Tag()
            tag.load(copy(self._mutfile), self._tags.copy())
            return tag

        def delete(self):
            self._mutfile.delete()
            for z in self.usertags:
                del(self._tags[z])

        def _info(self):
            info = self._mutfile.info
            fileinfo = [('Path', self.filepath),
                        ('Size', str_filesize(int(self.size))),
                        ('Filename', self.filename),
                        ('Modified', self.modified)]
            apeinfo = [('Length', self.length)]
            attr = {
                'Channels': 'channels',
                'Version': 'version'}
            for k, v in attr.items():
                try:
                    apeinfo.append([k, unicode(getattr(info, v))])
                except AttributeError:
                    continue
            return [('File', fileinfo), ("%s Info" % self.filetype, apeinfo)]

        info = property(_info)

        def load(self, mutfile, tags):
            self._mutfile = mutfile
            self.filepath = tags.filepath
            self._tags = tags

        def link(self, filename, x = None):
            """Links the audio, filename
            returns self if successful, None otherwise."""
            try:
                tags, audio = self._init_info(filename, mutagen_file)
            except mutagen.apev2.APENoHeaderError:
                audio = mutagen_file()
                tags, audio = self._init_info(filename, None)
                audio.filename = tags['__filepath']

            if audio is None:
                return

            for z in audio:
                self._tags[z.lower()] = audio.tags[z][:]

            self._tags.update(base_function(audio.info))
            self._tags.update(tags)
            self._set_attrs(attrib_fields)
            self._mutfile = audio
            return self

        def save(self):
            if self._mutfile.tags is None:
                self._mutfile.add_tags()
            if self.filepath != self._mutfile.filename:
                self._mutfile.filename = self.filepath
            audio = self._mutfile

            newtag = {}
            for tag, value in usertags(self._tags).items():
                try:
                    newtag[tag] = value
                except AttributeError:
                    pass
            toremove = [z for z in audio if z not in newtag and audio[z].kind == 0]
            for z in toremove:
                del(audio[z])
            audio.tags.update(newtag)
            audio.save()
    return Tag

def base_tags(info):
    tags = {'__filetype': 'APEv2',
        u"__length": strlength(info.length)}
    if hasattr(info, 'sample_rate'):
        tags.update(
            {u"__frequency": strfrequency(info.sample_rate)})
    return tags

Tag = get_class(APEv2File, base_tags, ATTRIBUTES)

filetype = (APEv2File, Tag , u'APEv2')