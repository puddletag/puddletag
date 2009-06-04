# -*- coding: utf-8 -*-
#__init__.py

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
#Foundation, Inc., 51  Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


import mutagen, time, pdb, calendar, os
from errno import ENOENT
from decimal import Decimal
from copy import copy, deepcopy
from os import path, stat

from stat import ST_SIZE, ST_MTIME, ST_CTIME, ST_ATIME

PATH = u"__path"
FILENAME = u"__filename"
READONLY = ('__bitrate', '__frequency', "__length", "__modified", "__size", "__created", "__library")
INFOTAGS = [PATH, FILENAME, "__ext", "__folder"]
INFOTAGS.extend(READONLY)

MIMETYPE = 'mime'
DESCRIPTION = 'description'
DATA = 'data'
IMAGETYPE = 'imagetype'

IMAGETAGS = (MIMETYPE, DESCRIPTION, DATA, IMAGETYPE)

TAGS = {'TALB': 'album',
        'TBPM': 'bpm',
        'TCOM': 'composer',
        'TCON': 'genre',
        'TCOP': 'copyright',
        'TDEN': 'encodingtime',
        'TDLY': 'playlistdelay',
        'TDOR': 'originaldate',
        'TDRC': 'year',
        'TDRL': 'releasetime',
        'TDTG': 'taggingtime',
        'TENC': 'encodedby',
        'TEXT': 'lyricist',
        'TFLT': 'filetype',
        'TIT1': 'grouping',
        'TIT2': 'title',
        'TIT3': 'version',
        'TKEY': 'initialkey',
        'TLAN': 'language',
        'TLEN': 'length',
        'TMED': 'mediatype',
        'TMOO': 'mood',
        'TOAL': 'originalalbum',
        'TOFN': 'originalfilename',
        'TOLY': 'author',
        'TOPE': 'originalartist',
        'TOWN': 'fileowner',
        'TPE1': 'artist',
        'TPE2': 'performer',
        'TPE3': 'conductor',
        'TPE4': 'arranger',
        'TPOS': 'discnumber',
        'TPRO': 'producednotice',
        'TPUB': 'organization',
        'TRCK': 'track',
        'TRSN': 'radiostationname',
        'TRSO': 'radioowener',
        'TSOA': 'albumsortorder',
        'TSOP': 'performersortorder',
        'TSOT': 'titlesortorder',
        'TSRC': 'isrc',
        'TSSE': 'encodingsettings',
        'TSST': 'setsubtitle',}
REVTAGS = dict([reversed(z) for z in TAGS.items()])


IMAGETYPES = ['Other', 'File Icon', 'Other File Icon', 'Cover (front)', 'Cover (back)',
'Leaflet page','Media (e.g. label side of CD)','Lead artist','Artist',
'Conductor', 'Band', 'Composer','Lyricist', 'Recording Location', 'During recording',
'During performance', 'Movie/video screen capture', 'A bright coloured fish', 'Illustration',
'Band/artist logotype', 'Publisher/Studio logotype']

splitext = lambda x: path.splitext(x)[1][1:].lower()

def stringtags(tag, leaveNone = False):
    """Takes a dictionary(tag) and returns string representations of each key.
    If a key is a list then the first item of that list is returned."""

    #Created this function, because a lot of puddletag's functions expects dicts with
    #only string items. So, rather than rewriting every function to do something like this, I use this.
    newtag = {}
    for i in tag:
        v = tag[i]
        if isinstance(v, basestring):
            newtag[i] = v
        elif not isinstance(i, int) and hasattr(v, '__iter__'):
            newtag[i] = v[0]
        elif isinstance(i, basestring) and leaveNone:
            newtag[i] = v
    return newtag

def strlength(value):
    """Converts seconds to length in minute:seconds format."""
    seconds = long(value % 60)
    if seconds < 10:
        seconds = u"0" + unicode(seconds)
    return "".join([unicode(long(value/60)),  ":", unicode(seconds)])

def strbitrate(bitrate):
    """Returns a string representation of bitrate in kb/s."""
    return unicode(bitrate/1000) + u' kb/s'

def strfrequency(value):
    return unicode(value / 1000.0)[:4] + u" kHz"

def lnglength(value):
    """Converts a string representation of length to seconds."""
    (minutes, seconds) = value.split(':')
    (minutes, seconds) = (long(minutes), long(seconds))
    return (minutes * 60) + seconds

def lngfrequency(value):
    """Inverse of strfrequency."""
    return long(Decimal(value.split(" ")[0]) * 1000)

def strtime(seconds):
    """Converts UNIX time(in seconds) to more Human Readable format."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))

def lngtime(value):
    '''Converts time in %Y-%m-%d %H:%M:%S format to seconds.'''
    return calendar.timegm(time.strptime(value, '%Y-%m-%d %H:%M:%S'))

def getfilename(filename):
    try:
        return unicode(path.realpath(filename), 'utf8')
    except:
        return path.realpath(filename)

def getinfo(filename):
    fileinfo = stat(filename)
    return ({FILENAME: filename,
            PATH: unicode(path.basename(filename)),
            u"__folder": unicode(path.dirname(filename)),
            u"__ext": unicode(path.splitext(filename)[1][1:]),
            u"__modified": strtime(fileinfo[ST_MTIME]),
            u"__size" : unicode(fileinfo[ST_SIZE]),
            u"__created": strtime(fileinfo[ST_CTIME]),
            u'__accessed': strtime(fileinfo[ST_ATIME])})

def converttag(tags):
    for tag,value in tags.items():
        if (tag not in INFOTAGS) and (isinstance(value, (basestring, int, long))):
            tags[tag] = [value]
        else:
            tags[tag] = value
    return tags

def usertags(tags):
    return dict([(z,v) for z,v in tags.items() if
                    not (isinstance(z, (int, long)) or z.startswith('__'))])
class MockTag(object):
    """Use as base for all tag classes."""
    def __init__(self, filename = None):
        if filename:
            self.link(filename)

    def update(self, dictionary=None, **kwargs):
        if dictionary is None:
            return
        if isinstance(dictionary, (dict, MockTag)):
            for key, value in dictionary.items():
                self[key] = value
        else:
            for key, value in dictionary:
                self[key] = value

    def __delitem__(self, key):
        if key in self._tags and key not in INFOTAGS:
            del(self._tags[key])

    def clear(self):
        keys = self._tags.keys()
        for z in keys:
            if z not in INFOTAGS and not z.startswith('___'):
                del(self._tags[z])

    def keys(self):
        return self._tags.keys()

    def values(self):
        return [self[key] for key in self]

    def items(self):
        return [(key, self[key]) for key in self]

    tags = property(lambda self: dict(self.items()))

    def __iter__(self):
        return self._tags.__iter__()

    def __contains__(self, key):
        return self._tags.__contains__(key)

    def __len__(self):
        try:
            return self._tags.__len__()
        except AttributeError:
            return 0 #This means that that bool(self) = False

    def stringtags(self):
        return stringtags(self)

    def save(self):
        if not path.exists(self.filename):
            raise IOError(ENOENT, os.strerror(ENOENT), self.filename)

    def usertags(self):
        return usertags(self)