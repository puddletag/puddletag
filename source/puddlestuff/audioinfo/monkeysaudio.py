# -*- coding: utf-8 -*-
from mutagen.monkeysaudio import MonkeysAudio

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
                getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY,
                FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created', 'bitrate',
    'modified', 'frequency', 'version', 'channels', 'filetype')

from apev2 import get_class

base = get_class(MonkeysAudio, u"Monkey's Audio", ATTRIBUTES)

class Tag(base):

    def _info(self):
        info = self.mut_obj.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]
        mpinfo = [('Bitrate', u'Lossless'),
                   ('Frequency', self.frequency),
                   ('Channels', unicode(info.channels)),
                   ('Length', self.length),
                   ('Stream Version', unicode(info.version))]
        return [('File', fileinfo), ("Monkeys Audio", mpinfo)]
    
    info = property(_info)

filetype = (MonkeysAudio, Tag, 'APEv2')