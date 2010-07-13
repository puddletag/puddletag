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

from mutagen.musepack import Musepack

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
                getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY,
                FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created',
              'modified', 'frequency', 'bitrate', 'version', 'channels')

from apev2 import get_class


def base_tags(info):
    tags = {
        u"__length": strlength(info.length),
        u"__frequency": strfrequency(info.sample_rate),
        u'__bitrate': u'%s kb/s' % info.bitrate,
        u'__version': unicode(info.version),
        u'__channels': unicode(info.channels),
        u'__filetype': u'MusePack'}
    try:
        tags.update({
            u'__titlegain': info.title_gain,
            u'__albumgain': info.album_gain})
    except AttributeError:
        pass
    return tags

base = get_class(Musepack, base_tags, ATTRIBUTES)
class Tag(base):

    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Path', self.filepath),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self.filename),
                    ('Modified', self.modified)]
        mpinfo = [('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Channels', unicode(info.channels)),
                   ('Length', self.length),
                   ('Stream Version', unicode(info.version))]
        return [('File', fileinfo), ("Musepack Info", mpinfo)]
    
    info = property(_info)

filetype = (Musepack, Tag, 'Musepack')