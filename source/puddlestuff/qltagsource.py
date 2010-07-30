#! /usr/bin/env python
# -*- coding: utf-8 -*-

#Copyright (C) 2008-2009 concentricpuddle

#This file is part of puddletag, a semi-good music tag editor.

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
import sys, pdb, os, time
from puddlestuff.puddleobjects import gettags, getfiles, PuddleConfig
from collections import defaultdict
from puddlestuff.constants import TAGSOURCE, HOMEDIR, TEXT, COMBO, CHECKBOX
from puddlestuff.util import matching, split_by_tag
from puddlestuff.tagsources import set_status, write_log
from puddlestuff.audioinfo import stringtags
from puddlestuff.libraries.quodlibetlib import QuodLibet

properties = {'type': TAGSOURCE}

def equal(audio1, audio2, play=False, tags=('artist', 'album')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if u''.join(audio1[key]).lower() != u''.join(audio2[key]).lower():
                return False
        else:
            return False
    if play and 'play' not in audio2:
        return False
    return True

class Example(object):
    name = 'QuodLibet'
    group_by = ['artist', 'album']
    counter = 0

    def __init__(self):
        object.__init__(self)
        self.lib = QuodLibet(os.path.join(HOMEDIR, 
            '.quodlibet/songs'))

    def search(self, artist, albums):
        ret = []
        matches = {}
        if artist in self.lib.artists:
            lib_albums = self.lib.get_albums(artist)
            get_info = lambda album: {'artist': artist, 'album': album}
            return [(get_info(album), []) for album in lib_albums]

    def retrieve(self, info):
        artist = info['artist']
        album = info['album']
        return info, [z.usertags for z in self.lib.get_tracks(
            'artist', artist, 'album', album)]

info = [Example, None]
name = 'QuodLibet'

if __name__ == '__main__':
    x = Example()
    d = x.search('Angie Stone', ['The Very Best Of'])
    print x.retrieve(d[0][0])
    