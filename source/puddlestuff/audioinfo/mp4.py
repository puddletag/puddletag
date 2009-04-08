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

import puddlestuff.audioinfo as audioinfo
from puddlestuff.audioinfo import converttag, converttag, strlength, strbitrate, strfrequency, lnglength, lngfrequency,strtime, lngtime, getinfo, FILENAME, PATH, INFOTAGS, READONLY
import pdb
from copy import copy, deepcopy

try:
    from mutagen.mp4 import MP4
except ImportError:
    from mutagen.m4a import M4A as MP4

TAGS = {'\xa9nam': 'title',
'\xa9alb': 'album',
'\xa9ART': 'artist',
'aART': 'albumartist',
'\xa9wrt': 'composer',
'\xa9day': 'year',
'\xa9cmt': 'comment',
'desc': 'description',
'purd': 'purchasedate',
'\xa9grp': 'grouping',
'\xa9gen': 'genre',
'\xa9lyr': 'lyrics',
'purl': 'podcasturl',
'egid': 'podcastepisodeguid',
'catg': 'podcastcategory',
'keyw': 'podcastkeywords',
'\xa9too': 'encodedby',
'cprt': 'copyright',
'soal': 'albumsortorder',
'soaa': 'albumartistsortorder',
'soar': 'artistsortorder',
'sonm': 'titlesortorder',
'soco': 'composersortorder',
'sosn': 'showsortorder',
'tvsh': 'showname',
'cpil': 'partofcompilation',
'pgap': 'partofgaplessalbum',
'pcst': 'podcast',
'trkn': 'track',
'disk': 'discnumber',
'tmpo': 'bpm'}
REVTAGS = dict([reversed(z) for z in TAGS.items()])

def getbool(value):
    if value:
        return [u'Yes']
    else:
        return [u'No']

def setbool(value):
    if value == 'No':
        return False
    elif value:
        return True
    else:
        return False

if MP4.__name__ == 'M4A':
    def settext(text):
        if isinstance(text, str):
            return unicode(text)
        elif isinstance(text, unicode):
            return text
        else:
            try:
                return text[0]
            except:
                print text
                pdb.set_trace()
                return text[0]

    def gettext(text):
        return [text]

    def settuple(value):
        if isinstance(value, tuple):
            return value
        elif isinstance(value, basestring):
            values = [z.strip() for z in value.split(u'/')]
            try:
                return tuple([int(z) for z in values[:2]])
            except (TypeError, IndexError):
                return None
        elif isinstance(value[0], basestring):
            return settuple(value[0])
        elif isinstance(value[0], tuple):
            return value[0]
        else:
            return value

    def gettuple(value):
        return [unicode(value[0]) + u'/' + unicode(value[1])]

    def getint(value):
        try:
            return [unicode(int(value))]
        except TypeError:
            return u"0"

    def setint(value):
        if isinstance(value, (int, long, basestring)):
            return int(value)
        else:
            return int(value[0])

    def getimg(value):
        return value

    def setimg(value):
        if 'data' in value:
            return [value]
        else:
            return [value[:1]]

else:
    def settext(text):
        if isinstance(text, str):
            return [unicode(text)]
        elif isinstance(text, unicode):
            return [text]
        else:
            return [unicode(z) for z in text]

    def gettext(value):
        return value

    def settuple(value):
        temp = []
        for tup in value:
            if isinstance(tup, basestring):
                values = [z.strip() for z in tup.split(u'/')]
                try:
                    temp.append(tuple([int(z) for z in values][:2]))
                except (TypeError, IndexError):
                    continue
            else:
                temp.append(tup)
        return temp

    def gettuple(value):
        return [unicode(track) + u'/' + unicode(total) for track, total in value]

    def getint(value):
        return [unicode(z) for z in value]

    def setint(value):
        temp = []
        for z in value:
            try:
                temp.append(int(z))
            except TypeError:
                continue
        return temp

    def getimg(value):
        return value

    def setimg(value):
        if 'data' in value:
            return [value]
        return value

FUNCS = {'title': (gettext, settext),
'album': (gettext, settext),
'artist': (gettext, settext),
'albumartist': (gettext, settext),
'composer': (gettext, settext),
'year': (gettext, settext),
'comment': (gettext, settext),
'description': (gettext, settext),
'purchasedate': (gettext, settext),
'grouping': (gettext, settext),
'genre': (gettext, settext),
'lyrics': (gettext, settext),
'podcastURL': (gettext, settext),
'podcastepisodeGUID': (gettext, settext),
'podcastcategory': (gettext, settext),
'podcastkeywords': (gettext, settext),
'encodedby': (gettext, settext),
'copyright': (gettext, settext),
'albumsortorder': (gettext, settext),
'albumartistsortorder': (gettext, settext),
'artistsortorder': (gettext, settext),
'titlesortorder': (gettext, settext),
'composersortorder': (gettext, settext),
'showsortorder': (gettext, settext),
'showname': (gettext, settext),
'partofcompilation': (getbool, setbool),
'partofgaplessalbum': (getbool, setbool),
'podcast': (getbool, setbool),
'track': (gettuple, settuple),
'discnumber': (gettuple, settuple),
'bpm': (getint, setint)}

class Tag(audioinfo.MockTag):
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

    File info tags like length start with '__'.
    Images can be accessed by either the '__image' tag or via Tag.images. Note
    that images aren't included when iterating through Tag.

    Use save to save tags."""

    def __init__(self,filename=None):
        """Links the audio"""
        if filename is not None:
            self.link(filename)

    def link(self, filename):

        """Links the audio, filename
        returns self if successful, None otherwise."""
        tags = getinfo(filename)
        filename = tags[FILENAME]
        audio = MP4(filename)
        self._tags = {}
        if audio is None:
            return
        self._freeform = {}

        if audio.tags: #Not empty
            keys = audio.keys()
            try:
                self.images = setimg([{'data': z} for z in audio['covr']])
                keys.remove('covr')
            except KeyError:
                self.images = None

            for z in keys:
                if z in TAGS:
                    self[TAGS[z]] = audio[z]
                else:
                    tag = z[z.find(':', z.find(':') +1) + 1:]
                    self._freeform[tag] = z
                    self._tags[tag] = audio[z]

        info = audio.info
        try:
            self._tags.update( {u"__frequency": strfrequency(info.sample_rate),
                        u"__length": strlength(info.length),
                        u"__bitrate": strbitrate(info.bitrate),
                        u'__channels': unicode(info.channels),
                        u'__bitspersample': unicode(info.bits_per_sample)})
        except AttributeError:
            #old mutagen version
            self._tags.update({u"__frequency": '0 kHz',
                        u"__length": strlength(info.length),
                        u"__bitrate": strbitrate(info.bitrate)})
        self._tags.update(tags)
        self.filename = tags[FILENAME]
        self._mutfile = audio
        self._originaltags = audio.keys()

    def load(self, tags, mutfile, originals, images = None):
        """Used only for creating a copy of myself."""
        self._tags = deepcopy(tags)
        self.filename = tags[FILENAME]
        self.images = deepcopy(images)
        self._originaltags = originals
        self._mutfile = mutfile

    def copy(self):
        tag = Tag()
        tag.load(self._tags.copy(), self._mutfile, copy(self._originaltags), copy(self.images))
        return tag

    def __getitem__(self,key):
        """Get the tag value from self._tags. There is a slight
        caveat in that this method will never return a KeyError exception.
        Rather it'll return ''."""
        if key == '__image':
            return self.images

        if key in INFOTAGS or isinstance(key, (int, long)):
            return self._tags[key]

        try:
            return FUNCS[key][0](self._tags[key])
        except KeyError:
            #This is a bit of a bother since there will never be a KeyError exception
            #But its needed for the sort method in tagmodel.TagModel, .i.e it fails
            #if a key doesn't exist.
            try:
                return gettext(self._tags[key])
            except KeyError:
                return ""

    def __setitem__(self,key,value):

        if isinstance(key, (int, long)):
            self._tags[key] = value
            return

        if key == '__image':
            self.images = setimg(value)
            return

        if key in INFOTAGS:
            self._tags[key] = value
            if key == FILENAME:
                self.filename = value
            return

        try:
            self._tags[key] = FUNCS[key][1](value)
        except KeyError:
            self._freeform[str(key)] = '----:net.sf.puddletag:' + str(key)
            self._tags[str(key)] = settext(value)

    def mutvalues(self):
        return [(key, self._tags[key]) for key in self if type(key) is not int and not key.startswith('__')]

    def save(self):
        """Writes the tags to file."""
        if self.filename != self._mutfile.filename:
            self._mutfile.filename = self.filename
        audio = self._mutfile

        newtag = {}
        if MP4.__name__ == "M4A":
            for tag, value in self.mutvalues():
                try:
                    newtag[REVTAGS[tag]] = value
                except KeyError:
                    newtag[self._freeform[tag]] = str(self._tags[tag])
                if self.images:
                    newtag['covr'] = self.images[0]['data']
        else:
            for tag, value in self.mutvalues():
                try:
                    newtag[REVTAGS[tag]] = value
                except KeyError:
                    newtag[self._freeform[tag]] = [str(z) for z in self._tags[tag]]
                except TypeError:
                    #Bool tags
                    newtag[REVTAGS[tag]] = value
            if self.images:
                newtag['covr'] = [z['data'] for z in self.images]

        toremove = [z for z in audio.keys() if z not in newtag]
        for key in toremove:
            del(audio[key])
        audio.tags.update(newtag)
        audio.save()

    def image(self, data, *args, **kwargs):
        return {'data': data}

filetype = (MP4, Tag)