# -*- coding: utf-8 -*-

from mutagen.musepack import Musepack

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
    getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY,
    FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created', 'filetype',
    'modified', 'frequency', 'bitrate', 'version', 'channels')

from apev2 import get_class


def base_tags(info):
    tags = {
        u"__length": strlength(info.length),
        u"__frequency": strfrequency(info.sample_rate),
        u'__bitrate': u'%s kb/s' % info.bitrate,
        u'__version': unicode(info.version),
        u'__channels': unicode(info.channels),
        u'__filetype': u'MusePack (APEv2)'}
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
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]
        mpinfo = [('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Channels', unicode(info.channels)),
                   ('Length', self.length),
                   ('Stream Version', unicode(info.version))]
        return [('File', fileinfo), ("Musepack Info", mpinfo)]
    
    info = property(_info)

filetype = (Musepack, Tag, 'APEv2')