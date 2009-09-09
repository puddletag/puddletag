# -*- coding: utf-8 -*-
#id3.py

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
#Foundation, Inc., 51 Fr anklin St, Fifth Floor, Boston, MA  02110-1301  USA


import mutagen, mutagen.id3, mutagen.mp3, pdb, util
from copy import copy, deepcopy
APIC, TimeStampTextFrame, TextFrame, ID3  = mutagen.id3.APIC, mutagen.id3.TimeStampTextFrame, mutagen.id3.TextFrame, mutagen.id3.ID3
from util import  (strlength, strbitrate, strfrequency,
                                        getfilename, getinfo, FILENAME, PATH, INFOTAGS, READONLY)
import imghdr

class PuddleID3(ID3):
    """ID3 reader to replace mutagen's just to allow the reading of APIC
    tags with the same description, ala Mp3tag."""
    PEDANTIC = True
    def loaded_frame(self, tag):
        if len(type(tag).__name__) == 3:
            tag = type(tag).__base__(tag)
        i = 0
        while tag.HashKey in self:
            try:
                tag.desc = tag.desc + unicode(i)
            except AttributeError:
                break
            i += 1
        self[tag.HashKey] = tag

class PuddleID3FileType(mutagen.mp3.MP3):
    """See PuddleID3."""
    def add_tags(self, ID3=PuddleID3):
        mutagen.mp3.MP3.add_tags(self, ID3)

    def load(self, filename, ID3 = PuddleID3, **kwargs):
        mutagen.mp3.MP3.load(self, filename, ID3, **kwargs)

TAGS = util.TAGS
REVTAGS = util.REVTAGS

class Tag(util.MockTag):
    IMAGETAGS = (util.MIMETYPE, util.DESCRIPTION, util.DATA,
                                                        util.IMAGETYPE)
    def copy(self):
        tag = Tag()
        tag.load(self._tags.copy(), copy(self._mutfile), copy(self._images))
        return tag

    def __getitem__(self,key):
        """Get the tag value from self._tags. There is a slight
        caveat in that this method will never return a KeyError exception.
        Rather it'll return ''."""
        if key == '__image':
            return self.images

        elif key in INFOTAGS or isinstance(key,(int,long)):
            return self._tags[key]
        else:
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
            #But its needed for the sort method in tagmodel.TagModel, .i.e it fails
            #if a key doesn't exist.
            return ""

    def image(self, data, description = '', mime = '', imagetype=0):
        if not mime:
            t = imghdr.what(None, data)
            if t:
                mime = u'image/' + t
        return APIC(3, mime, imagetype, description, data)

    def _getImages(self):
        if self._images:
            return [{'data': image.data, 'description': image.desc,
                    'mime': image.mime, 'imagetype': image.type}
                                            for image in self._images]
        return []

    def _setImages(self, images):
        self._images = images

    images = property(_getImages, _setImages)

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""
        filename = getfilename(filename)
        audio = PuddleID3FileType(filename)
        tags = getinfo(filename)
        self._tags = {}
        self._images = []
        if audio is None:
            return

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
                self._images = x

            x = [z for z in audio if z.startswith("COMM")]
            if x:
                self._tags['comment'] = [x[0], audio[x[0]]]
                for comment in x[1:]:
                    self._tags[u'comment: ' + audio[comment].desc ] = [comment, audio[comment]]

        info = audio.info
        self._tags.update( {u"__frequency": strfrequency(info.sample_rate),
                      u"__length": strlength(info.length),
                      u"__bitrate": strbitrate(info.bitrate)})
        self._tags.update(tags)
        self.filename = tags[FILENAME]
        self._mutfile = audio
        self._originaltags = [z[0] for z in self.mutvalues()]

    def load(self, tags, mutfile, images = None):
        """Used only for creating a copy of myself."""
        self._tags = deepcopy(tags)
        self.filename = tags[FILENAME]
        if not images:
            self._images = []
        else:
            self._images = deepcopy(images)
        self._originaltags = tags.keys()
        self._mutfile = mutfile

    def mutvalues(self):
        #Retrieves key, value pairs according to id3.
        return [self._tags[key] for key in self if type(key) is not int and not key.startswith('__')]

    def save(self):
        """Writes the tags to file."""
        if self.filename != self._mutfile.filename:
            self._mutfile.tags.filename = self.filename
            self._mutfile.filename = self.filename
        audio = self._mutfile
        util.MockTag.save(self)

        for tag, value in self.mutvalues():
            audio[tag] = value
        vals = [z[0] for z in self.mutvalues()]
        toremove = [z for z in self._originaltags if z not in vals]

        images = [z for z in audio if z.startswith(u'APIC')]
        if self._images:
            newimages = []
            for image in self._images:
                try:
                    i = 0
                    while image.HashKey in newimages:
                        i += 1
                        image.desc += u' '*i #Pad with spaces so that each
                    audio[image.HashKey] = image
                    newimages.append(image.HashKey)
                except AttributeError:
                    "Don't write images with strings, but with APIC objects"
            [toremove.append(z) for z in images if z not in newimages]
        else:
            toremove.extend(images)

        for z in set(toremove):
            try:
                del(audio[z])
            except KeyError:
                continue

        audio.tags.filename = self.filename
        audio.tags.save(v1 = 2)
        self._originaltags = [z[0] for z in self.mutvalues()]

    def __setitem__(self,key,value):

        if isinstance(key, (int, long)):
            self._tags[key] = value
            return

        if key == '__image':
            self._images = value
            return

        if key in INFOTAGS:
            self._tags[key] = value
            if key == FILENAME:
                self.filename = value
            return

        if isinstance(value, (basestring, int, long)):
            value = [unicode(value)]
        else:
            value = [unicode(z) for z in value]

        if key in self._tags:
            oldvalue = self._tags[key][1]
            if isinstance(oldvalue, TimeStampTextFrame):
                value = [mutagen.id3.ID3TimeStamp(z) for z in value if unicode(mutagen.id3.ID3TimeStamp(z))]
                oldvalue.text = value
                oldvalue.encoding = 3
            elif isinstance(self._tags[key][1], TextFrame):
                oldvalue.text = value
                oldvalue.encoding = 3
        else:
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

filetype = (PuddleID3FileType, Tag)