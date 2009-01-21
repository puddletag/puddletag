"""
audioinfo.py

Copyright (C) 2008 concentricpuddle

This audio is part of puddletag, a semi-good music tag editor.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import mutagen, time, pdb, calendar
from decimal import Decimal
from copy import copy, deepcopy
from os import path, stat
from stat import ST_SIZE, ST_MTIME, ST_CTIME
from mutagen.id3 import APIC, TimeStampTextFrame, TextFrame
import mutagen.oggvorbis, mutagen.flac, mutagen.apev2, mutagen.mp3


PATH = u"__path"
FILENAME = u"__filename"
READONLY = ('__bitrate', '__frequency', "__length", "__modified", "__size", "__created", "__library")
INFOTAGS = [PATH, FILENAME, "__ext", "__folder"]
INFOTAGS.extend(READONLY)


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
        'TMCL': 'musiciancredits',
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
SUPPORTED = (mutagen.mp3.MP3, mutagen.oggvorbis.OggVorbis, mutagen.flac.FLAC, mutagen.apev2.APEv2)
(MP3, OGG, FLAC, APEV2) = range(len(SUPPORTED))
VORBISCOMMENT = (OGG, FLAC, APEV2)

def converttag(tag):
    """Takes a dictionary(tag) and returns string representations of each key.
    If a key is a list then the first item of that list is returned.

    #Created this function, because a lot of puddletag's functions expects dicts with
    only string items. So, rather than rewriting every function to do something like this, I use this."""
    newtag = {}
    for i in tag:
        v = tag[i]
        if isinstance(v, (unicode,str)):
            newtag[i] = v
        elif not isinstance(i, int) and hasattr(v, '__iter__'):
            newtag[i] = v[0]
    return newtag

def usertags(tag):
    return dict([(z,tag[z]) for z in tag if type(z) is not int and not z.startswith("__")])

def strlength(value):
    seconds = long(value % 60)
    if seconds < 10:
        seconds = u"0" + unicode(seconds)
    return "".join([unicode(long(value/60)),  ":", unicode(seconds)])

def strbitrate(value):
    return unicode(value/1000) + u' kb/s'

def strfrequency(value):
    return unicode(value / 1000.0)[:4] + u" kHz"

def lnglength(value):
    (minutes, seconds) = value.split(':')
    (minutes, seconds) = (long(minutes), long(seconds))
    return (minutes * 60) + seconds

def lngfrequency(value):
    return long(Decimal(value.split(" ")[0]) * 1000)

def strtime(seconds):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))

def lngtime(value):
    return calendar.timegm(time.strptime(value, '%Y-%m-%d %H:%M:%S'))

class Tag:
    """Class that operates on audio audio tags.
    Currently supports ogg and mp3 files.

    It can be used in two ways.

    >>>tag = audioinfo.Tag(filename)
    Gets the tags in the audio, filename
    as a dictionary in format {tag: value} in Tag._tags.

    On the other hand, if you have already created
    a tag object. Use link like so:

    >>>tag = audioinfo.Tag()
    >>>tag.link(filename)
    {'artist': "Artist", "track":"12", title:"Title", '__length':"5:14"}
    The tags are stored in tag._tags.

    File info tags like length start with '__'.
    Except for '__image', '__path', these tags are readonly.

    Use save to save tags."""
    images = None
    def __init__(self,filename=None):
        """Links the audio"""
        if filename is not None:
            self.link(filename)

    def load(self, tags, filetype, images):
        self._tags = deepcopy(tags)
        if isinstance(filetype, int):
            self.filetype = filetype
        else:
            self.filetype = SUPPORTED.index(filetype)

        self.filename = tags[FILENAME]
        self.images = deepcopy(images)
        self._originaltags = tags.keys()

    def link(self, filename):
        """Links the audio, filename
        returns and sets self._tags if successful."""

        #Get the type of audio and set
        #self.filetype to it.
        self.filetype = None
        self._tags = {}

        if isinstance(filename, SUPPORTED):
            audio = deepcopy(filename)
            filename = audio.filename
        else:
            if isinstance(filename, str): #Can't decode unicode
                filename = unicode(path.realpath(filename), 'utf-8')
            else:
                filename = path.realpath(filename)
            try:
                audio = mutagen.File(filename)
            except (IOError, ValueError):
                return

        if audio is None:
            return

        if isinstance(audio, SUPPORTED[MP3]):
            if audio.tags: #Not empty
                audio.tags.update_to_v24()
                try:
                    x = [z for z in audio if z.startswith("TXXX")]
                    for z in x:
                        self._tags[audio[z].desc] = [z, audio[z]]
                except (IndexError, AttributeError):
                    pass

                for tagval in audio:
                    if tagval in TAGS:
                        self._tags[TAGS[tagval]] = [tagval, audio[tagval]]

                #Get the image data.
                x = audio.tags.getall("APIC")
                if x:
                    self.images = x

                x = [z for z in audio if z.startswith("COMM")]
                if x:
                    self._tags['comment'] = [x[0], audio[x[0]]]
                    for comment in x[1:]:
                        self._tags[u'comment: ' + audio[comment].desc ] = [comment, audio[comment]]

        elif isinstance(audio, tuple([SUPPORTED[z] for z in VORBISCOMMENT])):
            for z in audio:
                self._tags[z.lower()] = audio.tags[z]
            if 'tracknumber' in self._tags:
                self._tags["track"] = copy(self._tags["tracknumber"])
                del(self._tags["tracknumber"])
            if hasattr(audio, 'Pictures'):
                self.images = audio.Pictures
        else:
            return

        self.filetype = list(SUPPORTED).index(type(audio))
        if self.filetype == MP3:
            self._originaltags = [z[0] for z in self.mutvalues()]
        else:
            self._originaltags = self._tags.keys()

        info = audio.info
        self.filename = path.realpath(filename)
        fileinfo = stat(filename)
        self._tags.update({FILENAME: self.filename,
                            PATH: unicode(path.basename(self.filename)),
                            u"__folder": unicode(path.dirname(self.filename)),
                            u"__ext": unicode(path.splitext(self.filename)[1][1:]),
                            u"__bitrate": strbitrate(info.bitrate),
                            u"__frequency": strfrequency(info.sample_rate),
                            u"__length": strlength(info.length),
                            u"__modified": strtime(fileinfo[ST_MTIME]),
                            u"__size" : unicode(fileinfo[ST_SIZE]),
                            u"__created": strtime(fileinfo[ST_CTIME])})

        if self.filetype != FLAC:
            self._tags[u"__bitrate"] = strbitrate(info.bitrate)
        else:
            self._tags[u"__bitrate"] = u'0' + u' kb/s'
        self._mutfile = audio
        return self


    def update(self, dictionary=None, **kwargs):
        if dictionary is None:
            return
        if isinstance(dictionary, (dict,Tag)):
            for key, value in dictionary.items():
                self[key] = value
        else:
            for key, value in dictionary:
                self[key] = value

    def __getitem__(self,key):
        """Get the tag value from self._tags"""
        if key == '__image':
            return self.images
        elif key in INFOTAGS or isinstance(key,(int,long)):
            return self._tags[key]
        elif self.filetype == MP3:
            try:
                val = self._tags[key][1]
                if isinstance(val, TimeStampTextFrame):
                    return [unicode(z) for z in val]
                elif isinstance(val, TextFrame):
                    return val.text
            except KeyError:
                pass

        try:
            return self._tags[key]
        except KeyError:
            #This is a bit of a bother since there will never be a KeyError exception
            #But its needed for the sort method in puddbleobject.TagModel, .i.e it fails
            #if a key doesn't exist.
            return ""


    def __delitem__(self, key):
        if key in self._tags and key not in INFOTAGS:
            del(self._tags[key])

    def __setitem__(self,key,value):
        if isinstance(key, (int, long)):
            self._tags[key] = value
            return

        if key in READONLY:
            return

        if key in [FILENAME, PATH, "__ext"]:
            self._tags[key] = value
            try:
                self.filename = self._tags[FILENAME]
            except KeyError:
                """"Sometimes you create a Tag object and just set values willy
                nilly, while forgetting to set the filename attribute."""
            self.filenamechanged = True
            return

        if key == '__image':
            self.images = value
            return

        if key in INFOTAGS:
            self._tags[key] = value
            return

        if (key in self._tags) and ((not value) or (not [z for z in value if z])):
            del(self._tags[key])
            return

        if self.filetype == MP3:
            if key in self._tags:
                if isinstance(value, (str,unicode, int, long)):
                    value = [unicode(value)]
                if isinstance(self._tags[key][1], TimeStampTextFrame):
                    value = [mutagen.id3.ID3TimeStamp(z) for z in value if unicode(mutagen.id3.ID3TimeStamp(z))]
                    if value:
                        self._tags[key][1].text = value
                elif isinstance(self._tags[key][1], TextFrame):
                    self._tags[key][1].text = value
            else:
                if isinstance(value, (str,unicode, int, long)):
                    value = [unicode(value)]
                try:
                    mut = getattr(mutagen.id3, REVTAGS[key])
                    if isinstance(mut, TimeStampTextFrame):
                        value = [mutagen.id3.ID3TimeStamp(z) for z in value if mutagen.id3.ID3TimeStamp(z)]
                        mut.text = value
                    elif issubclass(mut, TextFrame):
                        mut = mut(3, value)
                    self._tags[key] = [REVTAGS[key], mut]
                except KeyError:
                    if key.startswith('comment'):
                        comment = key.split('comment: ')
                        if len(comment) == 1:
                            self._tags['comment'] = ["", mutagen.id3.COMM(3, "XXX", "", value)]
                        else:
                            self._tags[key] = [comment[1], mutagen.id3.COMM(3, "XXX", comment[1], value)]
                    else:
                        self._tags[key] = [u'TXXX:' + key, mutagen.id3.TXXX(3, key, value)]

        elif self.filetype in VORBISCOMMENT:
            if isinstance(value, (str,unicode, int, long)):
                value = [unicode(value)]
            self._tags[key] = value
        else:
            self._tags[key] = value

    def copy(self):
        tag = Tag()
        tag.load(self._tags, self.filetype, self.images)
        return tag

    def clear(self):
        keys = self._tags.keys()
        for z in keys:
            if z not in INFOTAGS:
                del(self._tags[z])

    def keys(self):
        return self._tags.keys()

    def values(self):
        return [self[key] for key in self]

    def mutvalues(self):
        return [self._tags[key] for key in self if type(key) is not int and not key.startswith('__')]

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
        return converttag(self)

    def save(self, filename = None):
        """Writes the tags in self._tags
        to self.filename if no filename is specified."""
        if not filename:
            filename = self.filename

        if not path.exists(filename):
            raise IOError(2, u"No such file or directory.")

        if hasattr(self, 'filenamechanged'):
            audio = mutagen.File(unicode(filename))
        else:
            audio = self._mutfile

        if isinstance(audio, SUPPORTED[MP3]):
            for tag, value in self.mutvalues():
                audio[tag] = value
            vals = [z[0] for z in self.mutvalues()]
            toremove = [z for z in self._originaltags if z not in vals]

            if self.images:
                try:
                    images = audio.tags.getall('APIC')
                except AttributeError: #The tag is probably empty
                    images = []
                if images != self.images:
                    images = [z for z in audio if z.startswith(u'APIC')]
                    newimages = []
                    for image in self.images:
                        try:
                            audio[u'APIC:' + image.desc] = image
                            newimages.append(u'APIC:' + image.desc)
                        except AttributeError:
                            "Don't write images with strings, but with APIC objects"
                    [toremove.append(z) for z in images if z not in newimages]

            for z in set(toremove):
                try:
                    del(audio[z])
                except KeyError:
                    continue
            audio.save(v1 = 2)
            self._originaltags = [z[0] for z in self.mutvalues()]

        else:
            newtag = {}
            for tag, value in self._tags.items():
                try:
                    if not tag.startswith("__") and ([z for z in value if z]):
                        newtag[tag] = value
                except AttributeError:
                        pass
            if "track" in newtag:
                newtag["tracknumber"] = copy(newtag["track"])
                del newtag["track"]
            toremove = [z for z in audio if z not in newtag]
            for z in toremove:
                del(audio[z])
            audio.tags.update(newtag)
            audio.save()

