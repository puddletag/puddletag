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

from mutagen.wavpack import WavPack

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
                getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY,
                FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created',
              'modified', 'frequency', 'bitrate')

from apev2 import get_class

def base_tags(info):
    return {
        u"__length": strlength(info.length),
        u"__frequency": strfrequency(info.sample_rate),
        u'__version': unicode(info.version),
        u'__channels': unicode(info.channels),
        u'__bitrate': u'0 kb/s',
        u'__filetype': 'WavPack'}

base = get_class(WavPack, base_tags, ATTRIBUTES)

class Tag(base):

    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Path', self.filepath),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self.filename),
                    ('Modified', self.modified)]
        wpinfo = [('Frequency', self.frequency),
                  ('Channels', unicode(info.channels)),
                  ('Length', self.length),
                  ('Bitrate', 'Lossless')]
        return [('File', fileinfo), ("WavPack Info", wpinfo)]
    
    info = property(_info)

filetype = (WavPack, Tag, 'WavPack')