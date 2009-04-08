"""
__init__.py

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
from mutagen.oggvorbis import OggVorbis
import puddlestuff.audioinfo as audioinfo
from puddlestuff.audioinfo import stringtags, strlength, strbitrate, strfrequency, lnglength, lngfrequency,strtime, lngtime, getinfo, FILENAME, PATH, INFOTAGS, READONLY

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
        self.images = None
        if filename is not None:
            self.link(filename)

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""
        tags = getinfo(filename)
        filename = tags[FILENAME]
        audio = OggVorbis(filename)
        self._tags = {}
        if audio is None:
            return

        for z in audio:
            self._tags[z.lower()] = audio.tags[z]
        if 'tracknumber' in self._tags: #Vorbiscomment uses tracknumber instead of track.
            self._tags["track"] = self._tags["tracknumber"][:]
            del(self._tags["tracknumber"])

        info = audio.info
        self._tags.update({u"__frequency": strfrequency(info.sample_rate),
                    u"__length": strlength(info.length),
                    u"__bitrate": strbitrate(info.bitrate)})
        self._tags.update(tags)
        self.filename = tags[FILENAME]
        self._mutfile = audio
        self._originaltags = self._tags.keys()
        return self

    def __getitem__(self,key):
        """Get the tag value from self._tags. There is a slight
        caveat in that this method will never return a KeyError exception.
        Rather it'll return ''."""

        try:
            return self._tags[key]
        except KeyError:
            #This is a bit of a bother since there will never be a KeyError exception
            #But its needed for the sort method in tagmodel.TagModel, .i.e it fails
            #if a key doesn't exist.
            return ""


    def __setitem__(self,key,value):
        if key == FILENAME:
                self.filename = value
        elif (key not in INFOTAGS) and isinstance(value, (unicode, str, int, long)):
            value = [unicode(value)]
        self._tags[key] = value

    def mutvalues(self):
        return [(key,self._tags[key]) for key in self if type(key) is not int and not key.startswith('__')]

    def save(self):
        """Writes the tags in self._tags
        to self.filename if no filename is specified."""

        if self.filename != self._mutfile.filename:
            self._mutfile.filename = self.filename
        audio = self._mutfile

        newtag = {}
        for tag, value in self.mutvalues():
            try:
                newtag[tag] = value
            except AttributeError:
                pass
        if "track" in newtag:
            newtag["tracknumber"] = newtag["track"][:]
            del newtag["track"]
        toremove = [z for z in audio if z not in newtag]
        for z in toremove:
            del(audio[z])
        audio.tags.update(newtag)
        audio.save()
        self._mutfile = audio

    def load(self, mutfile, tags):
        self._mutfile = mutfile
        self.filename = tags[FILENAME]
        self._tags = tags

    def copy(self):
        tag = Tag()
        tag.load(self._mutfile, self._tags.copy())
        return tag

filetype = (OggVorbis, Tag)