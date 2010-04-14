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


import mutagen, time, pdb, calendar, os, logging
from errno import ENOENT
from decimal import Decimal
from copy import copy, deepcopy
from os import path, stat

from stat import ST_SIZE, ST_MTIME, ST_CTIME, ST_ATIME

PATH = u"__path"
FILENAME = u"__filename"
EXTENSION = '__ext'
DIRPATH = '__dirpath'
READONLY = ('__bitrate', '__frequency', "__length", "__modified",
            "__size", "__created", "__library", '__accessed', '__filetype')
FILETAGS = [PATH, FILENAME, EXTENSION, DIRPATH]
INFOTAGS = FILETAGS + list(READONLY)


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

def setmodtime(filepath, atime, mtime):
    mtime = lngtime(mtime)
    atime = lngtime(atime)
    os.utime(filepath, (atime, mtime))

def commonimages(imagedicts):
    if imagedicts:
        x = imagedicts[0]
    for image in imagedicts[1:]:
        if image != x:
            return 0
    if not x:
        return None
    return x

def commontags(audios):
    images = []
    imagetags = set()
    combined = {}
    tags = {}
    images = []
    imagetags = set()
    for audio in audios:
        if audio.IMAGETAGS:
            images.append(audio['__image'] if audio['__image'] else {})
        else:
            images.append({})
        imagetags = imagetags.union(audio.IMAGETAGS)
        audio = stringtags(audio.usertags)
        for tag, value in audio.items():
            if tag in combined:
                if combined[tag] == value:
                    tags[tag] += 1
            else:
                combined[tag] = value
                tags[tag] = 1
    combined['__image'] = commonimages(images)
    return combined, tags, imagetags

def stringtags(tag, leaveNone = False):
    """Takes a dictionary(tag) and returns string representations of each key.
    If a key is a list then the first item of that list is returned."""

    #Created this function, because a lot of puddletag's functions expects dicts with
    #only string items. So, rather than rewriting every function to do something like this, I use this.
    newtag = {}
    for i in tag:
        v = tag[i]
        if i in INFOTAGS:
            newtag[i] = v
            continue
        if isinstance(i, int):
            continue

        if leaveNone and ((not v) or (len(v) == 1 and not v[0])):
            newtag[i] = ''
            continue
        elif (not v) or (len(v) == 1 and not v[0]):
            continue

        if isinstance(v, basestring):
            newtag[i] = v
        elif isinstance(i, basestring) and not isinstance(v, basestring):
            newtag[i] = v[0]
        else:
            newtag[i] = v
    return newtag

def strlength(value):
    """Converts seconds to length in minute:seconds format."""
    seconds = long(value % 60)
    if seconds < 10:
        seconds = u"0" + unicode(seconds)
    if value/3600 >= 1:
        return '%d:%d:%s' % (long(value/3600), long(value % 3600 / 60), unicode(seconds))
    else:
        return "".join([unicode(long(value/60)),  ":", unicode(seconds)])

def strbitrate(bitrate):
    """Returns a string representation of bitrate in kb/s."""
    return unicode(bitrate/1000) + u' kb/s'

def strfrequency(value):
    return unicode(value / 1000.0)[:4] + u" kHz"

def lnglength(value):
    """Converts a string representation of length to seconds."""
    if len(value.split(':')) == 3:
        (hours, minutes, seconds) = value.split(':')
        (hours, minutes, seconds) = (long(hours), long(minutes), long(seconds))
        return (hours * 3600) + (minutes * 60) + seconds
    else:
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
    return ({u"__modified": strtime(fileinfo[ST_MTIME]),
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

def writeable(tags):
    return [z for z in tags if not z.starswith('___') or z.startswith('~')]

def isempty(value):
    if isinstance(value, (int, long)):
        return False

    if not value:
        return True

    try:
        return not [z for z in value if z or isinstance(z, (int, long))]
    except TypeError:
        return False

def getdeco(func):
    def f(self, key):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key])
        elif key in self.mapping:
            return ''
        return func(self, key)
    return f

def setdeco(func):
    def f(self, key, value):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key], value)
        return func(self, key, value)
    return f

def deldeco(func):
    def f(self, key):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key])
        return func(self, key)
    return f

def reversedict(d):
    return dict(((v,k) for k in d))

_sizes = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
def str_filesize(size):
    valid = [z for z in _sizes if size / (1024.0**z) > 1]
    val = max(valid)
    return '%.2f %s' % (size/(1024.0**val), _sizes[val])

class MockTag(object):
    """Use as base for all tag classes."""
    def __init__(self, filename = None):
        self._info = {}
        if filename:
            self.link(filename)

    def _getfilepath(self):
        return self._tags[PATH]

    def _setfilepath(self,  val):
        self._tags.update({PATH: val,
                           DIRPATH: path.dirname(val),
                           FILENAME: path.basename(val),
                           EXTENSION: path.splitext(val)[1][1:]})

    def _setext(self,  val):
        if val:
            self.filepath = u'%s%s%s' % (path.splitext(self.filepath)[0],
                                     path.extsep, val)
        else:
            self.filepath = path.splitext(self.filepath)[0]

    def _getext(self):
        return self._tags[EXTENSION]

    def _getfilename(self):
        return self._tags[FILENAME]

    def _setfilename(self, val):
        self.filepath = os.path.join(self.dirpath, val)

    def _getdirpath(self):
        return self._tags[DIRPATH]

    def _setdirpath(self, val):
        self.filepath = os.path.join(val,  self.filename)

    filepath = property(_getfilepath, _setfilepath)
    dirpath = property(_getdirpath, _setdirpath)
    ext = property(_getext, _setext)
    filename = property(_getfilename, _setfilename)

    def _set_attrs(self, attrs):
        tags = self._tags
        [setattr(self, z, tags['__%s' % z]) for z in attrs]

    def _init_info(self, filename, filetype):
        self._tags = {}
        filename = getfilename(filename)
        self.filepath = filename
        audio = filetype(filename)
        tags = getinfo(filename)
        return tags, audio

    def update(self, dictionary=None, **kwargs):
        if dictionary is None:
            return
        if isinstance(dictionary, (dict, MockTag)):
            for key, value in dictionary.items():
                self[key] = value
        else:
            logging.debug(unicode(dictionary))
            for key, value in dictionary:
                self[key] = value

    @deldeco
    def __delitem__(self, key):
        if key in self._tags and key not in INFOTAGS:
            del(self._tags[key])

    def clear(self):
        keys = self._tags.keys()
        for z in keys:
            if z not in INFOTAGS and not z.startswith('___'):
                del(self._tags[z])

    def keys(self):
        if not self.mapping:
            return self._tags.keys()
        else:
            revmapping = self.revmapping
            mapping = self.mapping
            ret = []
            for key in self._tags:
                if key in mapping:
                    ret.append(mapping[key])
                elif key in revmapping:
                    pass
                else:
                    ret.append(key)
            return ret

    def values(self):
        return [self[key] for key in self]

    def items(self):
        return [(key, self[key]) for key in self]

    tags = property(lambda self: dict(self.items()))

    def __iter__(self):
        return self.keys().__iter__()

    def __contains__(self, key):
        return key in self.keys()

    def __len__(self):
        try:
            return self._tags.__len__()
        except AttributeError:
            return 0 #This means that that bool(self) = False

    def stringtags(self):
        return stringtags(self)

    def save(self):
        if not path.exists(self.filepath):
            raise IOError(ENOENT, os.strerror(ENOENT), self.filepath)

    def _usertags(self):
        return usertags(self)

    usertags = property(_usertags)

    def get(self, key):
        try:
            return self[key]
        except KeyError:
            return None

    def real(self, key):
        if key in self.revmapping:
            return self.revmapping[key]
        return key