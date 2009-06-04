#flac.py

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

from mutagen.flac import FLAC
from util import (strlength, strbitrate, strfrequency,
                                    getfilename, getinfo, FILENAME, PATH, INFOTAGS)
import ogg

class Tag(ogg.Tag):
    """Flac Tag Class.

    Behaves like Tag class in ogg.py"""
    def __init__(self,filename=None):
        """Links the audio"""
        self.images = None
        if filename is not None:
            self.link(filename)

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""
        filename = getfilename(filename)
        audio = FLAC(filename)
        tags = getinfo(filename)
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
                    u"__length": strlength(info.length)})
        try:
            self._tags[u"__bitrate"] = strbitrate(info.bitrate)
        except AttributeError:
            self._tags[u"__bitrate"] = u'0 kb/s'

        self._tags.update(tags)
        self.filename = tags[FILENAME]
        self._mutfile = audio
        return self

filetype = (FLAC, Tag)