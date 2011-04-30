# -*- coding: utf-8 -*-
import string

from collections import defaultdict
from PyQt4.QtCore import QFile, QIODevice
from PyQt4.QtGui import QAction, QApplication
from StringIO import StringIO
from copy import copy, deepcopy
from audioinfo import (FILETAGS, setmodtime, PATH, FILENAME,
    EXTENSION, MockTag, DIRPATH, DIRNAME, fn_hash)
from errno import EEXIST
import os, pdb, re
from puddleobjects import encode_fn, decode_fn, safe_name, open_resourcefile
import puddlestuff.translations
translate = puddlestuff.translations.translate
import errno, traceback

ARTIST = 'artist'
ALBUM = 'album'

def rename_error_msg(e, filename):
    if isinstance(e, DirRenameError):
        traceback.print_exc()
        m = translate("Defaults", '<p>An error occured while '
            'renaming the directory <b>%1</b> to <i>%2</i>.</p>'
            '<p>Reason: <b>%3</b><br />'
            'File used: %4</p>')
        m = m.arg(e.oldpath).arg(e.newpath).arg(e.strerror)
        return m.arg(filename)
        
    elif isinstance(e, RenameError):
        traceback.print_exc()
        m = translate("Defaults", '<p>An error occured while '
            'renaming the file <b>%1</b> to <i>%2</i>.</p>'
            '<p>Reason: <b>%3</b></p>')
        return m.arg(e.oldpath).arg(e.newpath).arg(e.strerror)
    elif isinstance(e, EnvironmentError):
        traceback.print_exc()
        m = translate("Defaults",
            '<p>An error occured while writing to <b>%1</b>.</p>'
            '<p>Reason: <b>%2</b></p>')
        m = m.arg(filename).arg(e.strerror)
        return m

def rename(oldpath, newpath):
    if oldpath == newpath:
        return False
    if os.path.exists(newpath):
        raise RenameError(IOError(EEXIST, os.strerror(EEXIST),
            newpath), oldpath, newpath)
    if not os.path.exists(os.path.dirname(newpath)):
        try:
            os.makedirs(os.path.dirname(newpath))
        except EnvironmentError, e:
            e.strerror = translate('Errors', "Couldn't create "
                "intermediate directory: %s")
            e.strerror %= decode_fn(os.path.dirname(newpath))
            raise RenameError(e, oldpath, newpath)

    try:
        os.rename(oldpath, newpath)
        return True
    except EnvironmentError, e:
        raise RenameError(e, oldpath, newpath)

def rename_dir(filename, olddir, newdir):
    if newdir == olddir:
        return False
    try:
        os.renames(olddir, newdir)
        return True
    except EnvironmentError, e:
        raise DirRenameError(e, olddir, newdir)

class RenameError(EnvironmentError):
    def __init__(self, errno=None, strerror=None, filename=None):
        if isinstance(errno, Exception):
            e = errno
            EnvironmentError.__init__(self, e.errno, e.strerror, e.filename)
            self.oldpath = strerror
            self.newpath = filename
        else:
            EnvironmentError.__init__(self, errno, strerror, filename)
            self.oldpath = ''
            self.newpath = ''

class DirRenameError(RenameError): pass

def convert_dict(d, keys):
    d = deepcopy(d)
    for key in keys:
        if key in d:
            d[keys[key]] = d[key]
            del(d[key])
    return d

def equal(audio1, audio2, tags=('artist', 'album', 'title')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if to_string(audio1[key]) != to_string(audio2[key]):
                return False
        else:
            return False
    return True

def escape_html(txt):
    result = txt
    result = result.replace(u"&", u"&amp;")
    result = result.replace(u"<", u"&lt;")
    result = result.replace(u">", u"&gt;")
    return result

def fields_from_text(text):
    if not text:
        return []
    return filter(None, map(string.strip, text.split(u',')))

def matching(audios, listing):
    ret = {}
    for audio in audios:
        for tag in listing:
            if equal(audio, tag):
                ret[audio] = tag
    if len(audios) == len(ret):
        return ret, True
    return ret, False

def rename_file(audio, tags):
    """If tags(a dictionary) contains a PATH key, then the file
    in self.taginfo[row] is renamed based on that.

    If successful, tags is returned(with the new filename as a key)
    otherwise {} is returned."""
    test_audio = MockTag()
    test_audio.filepath = audio.filepath

    
    if PATH in tags:
        test_audio.filepath = to_string(tags[PATH])
    if FILENAME in tags:
        test_audio.filename = safe_name(to_string(tags[FILENAME]))
    if EXTENSION in tags:
        test_audio.ext = safe_name(to_string(tags[EXTENSION]))

    if rename(audio.filepath, test_audio.filepath):
        audio.filepath = test_audio.filepath

    if DIRNAME in tags:
        newdir = safe_name(encode_fn(tags[DIRNAME]))
        newdir = os.path.join(os.path.dirname(audio.dirpath),
            newdir)
        if rename_dir(audio.filepath, audio.dirpath, newdir):
            audio.dirpath = newdir
    elif DIRPATH in tags:
        newdir = encode_fn(tags[DIRPATH])
        if rename_dir(audio.filepath, audio.dirpath, newdir):
            audio.dirpath = newdir

def split_by_tag(tracks, main='artist', secondary='album'):
    if secondary:
        ret = defaultdict(lambda: defaultdict(lambda: []))
        [ret[to_string(track.get(main))]
            [to_string(track.get(secondary))].append(track) for track in tracks]
    else:
        ret = defaultdict(lambda: [])
        [ret[to_string(track.get(main))].append(track) for track in tracks]
    return ret

split_by_field = split_by_tag

def sorted_split_by_field(tracks, field='artist'):
    """Splits the tracks by field, but preserves order.

    Returns a list of two-tuples:
        (value, all files with track[field] == value)"""
    indexes = {}
    ret = []
    for track in tracks:
        main_val = to_string(track.get(field, u""))
        if main_val in indexes:
            ret[indexes[main_val]][1].append(track)
        else:
            index = len(ret)
            indexes[main_val] = index
            ret.append([main_val, [track]])
    return ret

def to_list(value):
    if isinstance(value, (str, int, long)):
        value = [unicode(value)]
    elif isinstance(value, unicode):
        value = [value]
    return value

def to_string(value):
    if not value:
        return u''
    elif isinstance(value, str):
        return value.decode('utf8')
    elif isinstance(value, unicode):
        return value
    else:
        return to_string(value[0])

def write(audio, tags, save_mtime = True, justrename=False):
    """A function to update one row.
    row is the row, tags is a dictionary of tags.

    If undo`is True, then an undo level is created for this file.
    If justrename is True, then (if tags contain a PATH or EXTENSION key)
    the file is just renamed i.e not tags are written.
    """
    tags = deepcopy(tags)
    if audio.library and (ARTIST in tags or ALBUM in tags):
        artist = audio.get(ARTIST, u'')
    else:
        artist = None

    preview = {}
    if audio.preview:
        preview = audio.preview
        audio.preview = {}

    fn_fields = dict((key, tags[key]) for key in FILETAGS if key in tags)

    undo = dict([(field, copy(audio.get(field, [])))
        for field in tags if
            (field not in fn_fields and 
                tags.get(field, u'') != audio.get(field, u''))])

    oldimages = None
    if '__image' in tags:
        if not audio.IMAGETAGS:
            del(tags['__image'])
        else:
            oldimages = audio['__image']

    try:
        if fn_fields:
            for key in fn_fields:
                if key in fn_hash:
                    undo[key] = getattr(audio, fn_hash[key])
            rename_file(audio, fn_fields)
        if not justrename:
            user_only = without_file(tags)
            if user_only:
                audio.update(user_only)
                audio.save()
    except EnvironmentError:
        audio.update(undo)
        audio.preview = preview
        if oldimages is not None:
            audio['__image'] = oldimages
        raise
    if save_mtime:
        try:
            setmodtime(audio.filepath, audio.accessed, audio.modified)
        except EnvironmentError:
            pass
    return undo

def real_filetags(mapping, revmapping, tags):
    filefields = [mapping.get(key, key) for key in FILETAGS]
    return dict([(revmapping.get(key, key), tags[key]) for key in filefields if key in tags])

def separator(parent=None):
    s = QAction(parent)
    s.setSeparator(True)
    return s

def without_file(tags):
    return dict([(key, tags[key]) for key in tags if key not in FILETAGS])

class PluginFunction(object):
    def __init__(self, name, function, pprint, args=None, desc=None):
        self.name = name
        self.function = function
        self.func_code = function.func_code
        self.print_string = pprint
        self.desc = desc
        self.args = args
        if not args:
            return
        newargs = []
        for arg in args:
            arg = list(arg)
            if arg[1] == puddlestuff.constants.CHECKBOX:
                arg[2] = unicode(bool(arg[2]))
            newargs.append(arg)
        self.args = newargs

    def __call__(self, *args):
        return self.function(*args)