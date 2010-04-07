#! /usr/bin/env python

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
import sys, pdb, os
sys.path.insert(1, '/home/keith/Documents/python/puddletag')
from puddlestuff.puddleobjects import gettags, getfiles
from collections import defaultdict

musicdir = '/mnt/multimedia/Music'
dirs = [unicode(z, 'utf8') for z in os.listdir(musicdir)]

def separate(tags):
    #artist = tags.real('artist')
    #album = tags.real('album')
    artist = 'artist'
    album = 'album'
    ret = defaultdict(lambda:set())
    [ret[tag[artist][0] if artist in tag else ''].add(
            tag[album][0] if album in tag else '') for tag in tags]
    return ret

class Example(object):
    def search(self, audios=None, params=None):
        self._artistids = {}
        self._releases = {}
        ret = defaultdict(lambda:{})
        if not params:
            params = separate(audios)
        for artist, albums in params.items():
            if artist:
                albumtuple = [z.split(u' - ', 2) for z in dirs if z.startswith(artist)]
                releases = []
                for z in albumtuple:
                    if len(z) > 1:
                        releases.append(z[1])
                ret[artist]['__albumlist'] = dict([(z, []) for z in releases])
                for album in releases:
                    ret[artist][album] = []
        return ret

    def retrieve(self, artist, album):
        dirpath = u'%s/%s - %s' % (musicdir, artist, album)
        files = getfiles(dirpath)
        return [z.stringtags() for z in gettags(files) if z], {}

if __name__ == '__main__':
    x = Example()
    #print x.search([{'artist': ['Linkin Park'], 'album': ['Midnight']}])
    print x.retrieve('Linkin Park', 'Minutes to Midnight')