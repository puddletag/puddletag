# -*- coding: utf-8 -*-
#mp4.py

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


import util
from util import (usertags, strlength, strbitrate, READONLY, isempty,
                    getfilename, strfrequency, getinfo, FILENAME, PATH, INFOTAGS)
from copy import copy, deepcopy
from mutagen.mp4 import MP4,  MP4Cover

#mp4 tags, like id3 can only have a fixed number of tags. The ones on the left
#with the corresponding tag as recognized by puddletag on the right...

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
'tmpo': 'bpm'}

REVTAGS = dict([reversed(z) for z in TAGS.items()])

#Because these values are storted in different ways, text for album, tuple
#for tracks, I created to a bunch of functions, to handle the reading
#and writing of these.

#Functions are in get and set pairs.
#get functions take a value mutagen expects it and returns it in puddletag's format.
#set functions do the opposite.

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
    if isinstance(value, (int, long, basestring)):
        return [int(value)]
    temp = []
    for z in value:
        try:
            temp.append(int(z))
        except ValueError:
            continue
    return temp

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
'track': (getint, setint),
'disc': (getint, setint),
'totaltracks': (getint, setint),
'totaldiscs': (getint, setint),
'bpm': (getint, setint)}

class Tag(util.MockTag):
    """Class for Mp4 tags.

    Do not use unicode! It's fucked."""
    IMAGETAGS = (util.MIMETYPE, util.DATA)
    def copy(self):
        tag = Tag()
        tag.load(self._tags.copy(), copy(self._mutfile), copy(self.images))
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
            try:
                #First, check if a freeform user defined tag exists.
                return gettext(self._tags[key])
            except KeyError:
                return ""

    def __setitem__(self,key,value):
        if key in READONLY:
            return

        if isinstance(key, (int, long)):
            self._tags[key] = value
            return

        if key == '__image':
            self.images = value
            return

        if key in INFOTAGS:
            self._tags[key] = value
            if key == FILENAME:
                self.filename = value
            return

        if key not in INFOTAGS and isempty(value):
            del(self[key])
            return

        try:
            self._tags[key] = FUNCS[key][1](value)
        except KeyError:
            #User defined tags.
            self._freeform[str(key)] = '----:net.sf.puddletag:' + str(key)
            self._tags[str(key)] = settext(value)

    def delete(self):
        self._mutfile.delete()
        for z in self.usertags:
            del(self._tags[z])
        self.images = []

    def image(self, data, mime, **kwargs):
        if mime.lower().endswith(u'png'):
            format = MP4Cover.FORMAT_PNG
        else:
            format = MP4Cover.FORMAT_JPEG
        return MP4Cover(data, format)

    def _setImages(self, images):
        self._images = images

    def _getImages(self):
        temp = []
        for value in self._images:
            if value.format == MP4Cover.FORMAT_PNG:
                temp.append({'data': value, 'mime': 'image/png'})
            else:
                temp.append({'data': value, 'mime': 'image/jpeg'})
        return temp

    images = property(_getImages, _setImages)

    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Filename', self[FILENAME]),
                    ('Size', unicode(int(self['__size'])/1024) + ' kB'),
                    ('Path', self[PATH]),
                    ('Modified', self['__modified'])]

        mp4info = [('Bitrate', self['__bitrate']),
                   ('Frequency', self['__frequency']),
                   ('Channels', unicode(info.channels)),
                   ('Length', self['__length']),
                   ('Bits per sample', unicode(info.bits_per_sample))]

        return [('File', fileinfo), ('MP4 Info', mp4info)]

    info = property(_info)

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""
        filename = getfilename(filename)
        audio = MP4(filename)
        tags = getinfo(filename)
        self._tags = {}
        self._images = []

        if audio is None:
            return

        self._freeform = {} #Keys are tags as required by mutagen i.e. The '----'
                            #frames. Values are the tag as represented by puddletag.

        if audio.tags: #Not empty
            keys = audio.keys()
            try:
                self.images = audio['covr']
                keys.remove('covr')
            except KeyError:
                pass

            #I want 'trkn', to split into track and totaltracks, like Mp3tag.
            if 'trkn' in keys:
                self[u'track'] = [z[0] for z in audio['trkn']]
                self[u'totaltracks'] = [z[1] for z in audio['trkn']]
                keys.remove('trkn')

            #Same as above
            if 'disk' in keys:
                self[u'disc'] = [z[0] for z in audio['disk']]
                self[u'totaldiscs'] = [z[1] for z in audio['disk']]
                keys.remove('disk')

            for z in keys:
                if z in TAGS:
                    self[TAGS[z]] = audio[z]
                else:
                    tag = z[z.find(':', z.find(':') +1) + 1:]
                    self._freeform[tag] = z
                    self._tags[tag] = audio[z]

        info = audio.info
        self._tags.update( {u"__frequency": strfrequency(info.sample_rate),
                    u"__length": strlength(info.length),
                    u"__bitrate": strbitrate(info.bitrate),
                    u'__channels': unicode(info.channels),
                    u'__bitspersample': unicode(info.bits_per_sample)})
        self._tags.update(tags)
        self.filename = filename
        self._mutfile = audio

    def load(self, tags, mutfile, images = None):
        """Used only for creating a copy of myself."""
        self._tags = deepcopy(tags)
        self.filename = tags[FILENAME]
        if not images:
            self.images = []
        else:
            self.images = deepcopy(images)
        self._mutfile = mutfile

    def save(self):
        if self.filename != self._mutfile.filename:
            self._mutfile.filename = self.filename
        audio = self._mutfile

        newtag = {}
        tuples = (('track', ['trkn', 'totaltracks']),
                  ('disc', ['disk', 'totaldiscs']))
        tags = self._tags
        for tag, values in tuples:
            if tag in tags:
                denom = tags[tag]
                if values[1] in tags:
                    total = tags[values[1]]
                    newtag[values[0]] = [(int(t), int(total)) for t, total in
                                                            zip(denom, total)]
                else:
                    newtag[values[0]] = [(int(z), 0) for z in denom]
            elif values[1] in tags:
                total = tags[values[1]]
                newtag[values[0]] = [(0, int(z)) for z in total]

        tags = usertags(self._tags)
        tags = [(z, tags[z]) for z in tags
                    if z not in ['track', 'totaltracks', 'disc', 'totaldiscs']]

        for tag, value in tags:
            try:
                newtag[REVTAGS[tag]] = value
            except KeyError:
                newtag[self._freeform[tag]] = [str(z) for z in self._tags[tag]]

        if self.images:
            newtag['covr'] = self._images

        toremove = [z for z in audio.keys() if z not in newtag]
        for key in toremove:
            del(audio[key])
        audio.update(newtag)
        audio.save()

filetype = (MP4, Tag)