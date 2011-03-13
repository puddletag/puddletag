# -*- coding: utf-8 -*-
from mutagen.monkeysaudio import MonkeysAudio

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
                getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY,
                FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created', 'bitrate',
    'modified', 'frequency', 'version', 'channels', 'filetype')

from apev2 import get_class


def base_tags(info):
    tags = {
        "__length": strlength(info.length),
        "__frequency": strfrequency(info.sample_rate),
        '__version': unicode(info.version),
        '__channels': unicode(info.channels),
        '__filetype': u"Monkey's Audio",
        '__bitrate': u'0 kb/s'}
    try:
        tags.update({
            '__titlegain': info.title_gain,
            '__albumgain': info.album_gain})
    except AttributeError:
        pass
    return tags

base = get_class(MonkeysAudio, base_tags, ATTRIBUTES)

class Tag(base):

    def _info(self):
        info = self._mutfile.info
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