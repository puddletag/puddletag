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
from util import *
import id3, flac, ogg, apev2, mp4
options = (id3.filetype, flac.filetype, ogg.filetype, apev2.filetype, mp4.filetype)
from mutagen.id3 import TCON
GENRES = sorted(TCON.GENRES)



e = {'mp3': id3.filetype,
    'flac': flac.filetype,
    'ogg': ogg.filetype,
    'mp4': mp4.filetype,
    'm4a': mp4.filetype,
    'ape': apev2.filetype}

mapping = {}
revmapping = {}

def loadmapping(filepath):
    try:
        lines = open(filepath, 'r').read().split('\n')
    except (IOError, OSError):
        return {'VorbisComment': {'tracknumber': 'track',
            'date': 'year'}}
    mappings = {}
    for l in lines:
        tags = [z.strip() for z in l.split(',')]
        if len(tags) == 3: #Tag, Source, Target
            try:
                mappings[tags[0]].update({tags[1].lower(): tags[2].lower()})
            except KeyError:
                mappings[tags[0]] = ({tags[1].lower(): tags[2].lower()})
    return mappings

def setmapping(m):
    global revmapping
    global mapping

    mapping = m
    for z in mapping:
        revmapping[z] = dict([(value,key) for key, value in mapping[z].items()])
    for z in e.values():
        try:
            if z[2] in mapping:
                z[1].mapping = mapping[z[2]]
                z[1].revmapping = revmapping[z[2]]
            if 'puddletag' in mapping:
                z[1].mapping.update(mapping['puddletag'])
                z[1].revmapping.update(revmapping['puddletag'])
        except IndexError:
            pass

setmapping({'VorbisComment': {'tracknumber': 'track'}})

def Tag(filename):
    """Class that operates on audio tags.
    Currently supports ogg, mp3, mp4, apev2 and flac files

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

    Use save to save tags.

    There are caveats associated with each module, so check out their docstrings
    for more info."""

    fileobj = file(filename, "rb")
    ext = splitext(filename)
    try:
        return e[ext][1](filename)
    except KeyError:
        pass

    try:
        header = fileobj.read(128)
        results = [Kind[0].score(filename, fileobj, header) for Kind in options]
    finally:
        fileobj.close()
    results = zip(results, options)
    results.sort()
    score, Kind = results[-1]
    if score > 0: return Kind[1](filename)
    else: return None