# -*- coding: utf-8 -*-
from collections import defaultdict
from PyQt4.QtCore import QFile, QIODevice
from StringIO import StringIO
from copy import copy
from audioinfo import FILETAGS, setmodtime, PATH, FILENAME, EXTENSION, MockTag
from errno import EEXIST
import os, pdb
from puddleobjects import safe_name

ARTIST = 'artist'
ALBUM = 'album'

def equal(audio1, audio2, tags=('artist', 'album', 'title')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if to_string(audio1[key]) != to_string(audio2[key]):
                return False
        else:
            return False
    return True

def matching(audios, listing):
    ret = {}
    for audio in audios:
        for tag in listing:
            if equal(audio, tag):
                ret[audio] = tag
    if len(audios) == len(ret):
        return ret, True
    return ret, False

def open_resourcefile(filename):
    f = QFile(filename)
    f.open(QIODevice.ReadOnly | QIODevice.Text)
    return StringIO(f.readAll())

def rename_file(audio, tags):
    """If tags(a dictionary) contains a PATH key, then the file
    in self.taginfo[row] is renamed based on that.

    If successful, tags is returned(with the new filename as a key)
    otherwise {} is returned."""
    test_audio = MockTag()
    test_audio.filepath = audio.filepath
    

    if FILENAME in tags:
        test_audio.filename = safe_name(to_string(tags[FILENAME]))
        returntag = FILENAME
    elif EXTENSION in tags:
        test_audio.ext = safe_name(to_string(tags[EXTENSION]))
        returntag = EXTENSION
    elif PATH in tags:
        returntag = PATH
        test_audio.filepath = tags[PATH]
    else:
        return

    newfilename = test_audio.filepath
    if newfilename != audio.filepath:
        if os.path.exists(newfilename):
            raise IOError(EEXIST, os.strerror(EEXIST), newfilename)
        elif not os.path.exists(test_audio.dirpath):
            os.makedirs(test_audio.dirpath)
        os.rename(audio.filepath, newfilename)
        audio.filepath = newfilename
    return returntag

def split_by_tag(tracks, main='artist', secondary='album'):
    if secondary:
        ret = defaultdict(lambda: defaultdict(lambda: []))
        [ret[to_string(track.get(main))]
            [to_string(track.get(secondary))].append(track) for track in tracks]
    else:
        ret = defaultdict(lambda: [])
        [ret[to_string(track.get(main))].append(track) for track in tracks]
    return ret

def to_string(value):
    if not value:
        return u''
    elif isinstance(value, str):
        return value.decode('utf8')
    elif isinstance(value, unicode):
        return value
    else:
        return to_string(value[0])

def write(audio, tags, save_mtime = True):
    """A function to update one row.
    row is the row, tags is a dictionary of tags.

    If undo`is True, then an undo level is created for this file.
    If justrename is True, then (if tags contain a PATH or EXTENSION key)
    the file is just renamed i.e not tags are written.
    """
    tags = copy(tags)
    if audio.library and (ARTIST in tags or ALBUM in tags):
        artist = audio.sget(ARTIST)
    else:
        artist = None

    preview = {}
    if audio.preview:
        preview = audio.preview
        audio.preview = {}

    undo = dict([(tag, copy(audio[tag])) if tag in audio
                    else (tag, []) for tag in tags])

    oldimages = None
    if '__image' in tags:
        if not hasattr(audio, 'image'):
            del(tags['__image'])
        else:
            oldimages = audio['__image']
            undo['__image'] = oldimages
            images = []
            for z in tags['__image']:
                images.append(dict([(key,val) for key,val in z.items()
                                        if key in audio.IMAGETAGS]))
            tags['__image'] = [audio.image(**z) for z in images]

    filetags = real_filetags(audio.mapping, audio.revmapping, tags)
    try:
        if filetags:
            rename_file(audio, filetags)
        audio.update(without_file(audio.mapping, tags))
        audio.save()
    except EnvironmentError:
        audio.update(undo)
        audio.preview = preview
        if oldimages is not None:
            audio['__image'] = oldimages
        raise
    if save_mtime:
        setmodtime(audio.filepath, audio.accessed,
                    audio.modified)
    return undo

def real_filetags(mapping, revmapping, tags):
    filefields = [mapping.get(key, key) for key in FILETAGS]
    return dict([(revmapping.get(key, key), tags[key]) for key in filefields if key in tags])

def without_file(mapping, tags):
    filefields = [mapping.get(key, key) for key in FILETAGS]
    return dict([(key, tags[key]) for key in tags if key not in filefields])

