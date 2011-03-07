# -*- coding: utf-8 -*-

from mutagen.wavpack import WavPack

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
    getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY,
    FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created',
    'modified', 'frequency', 'bitrate', 'filetype')

from apev2 import get_class

def base_tags(info):
    return {
        u"__length": strlength(info.length),
        u"__frequency": strfrequency(info.sample_rate),
        u'__version': unicode(info.version),
        u'__channels': unicode(info.channels),
        u'__bitrate': u'0 kb/s',
        u'__filetype': u'WavPack (APEv2)'}

base = get_class(WavPack, base_tags, ATTRIBUTES)

class Tag(base):

    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Path', self[ATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]
        wpinfo = [('Frequency', self.frequency),
                  ('Channels', unicode(info.channels)),
                  ('Length', self.length),
                  ('Bitrate', 'Lossless')]
        return [('File', fileinfo), ("WavPack Info", wpinfo)]
    
    info = property(_info)

filetype = (WavPack, Tag, 'APEv2')