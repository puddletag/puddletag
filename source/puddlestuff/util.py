import logging
import os
import shutil
import traceback
from collections import defaultdict
from copy import copy, deepcopy
from errno import EEXIST
from operator import itemgetter
from xml.sax.saxutils import escape as escape_html
from mutagen import MutagenError

from PyQt5.QtWidgets import QAction

from . import translations, constants
from .audioinfo import (FILETAGS, setmodtime, PATH, FILENAME,
                        EXTENSION, MockTag, DIRPATH, DIRNAME, READONLY, fn_hash, isempty, encode_fn, decode_fn)
from .constants import BLANK, SEPARATOR, LOG_FILENAME
from .puddleobjects import (issubfolder, safe_name)

translate = translations.translate

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
    elif isinstance(e, PermissionError):
        traceback.print_exc()
        m = translate("Defaults",
                      '<p>An error occured while writing to <b>%1</b>.</p>'
                      '<p>Reason: <b>%2</b>.</p>'
                      '<p>(<i>See %3 for debug info.</i>)</p>')
        m = m.arg(filename)
        m = m.arg(str(e) if e.strerror is None else e.strerror)
        m = m.arg(LOG_FILENAME)
        return m
    elif isinstance(e, EnvironmentError):
        traceback.print_exc()
        m = translate("Defaults",
                      '<p>An error occured while writing to <b>%1</b>.</p>'
                      '<p>Reason: <b>%2</b> ('
                      '<i>See %3 for debug info.</i>)</p>')
        m = m.arg(filename)
        m = m.arg(str(e) if e.strerror is None else e.strerror)
        m = m.arg(LOG_FILENAME)
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
        except EnvironmentError as e:
            e.strerror = translate('Errors', "Couldn't create "
                                             "intermediate directory: %s")
            e.strerror %= decode_fn(os.path.dirname(newpath))
            logging.exception(e.strerror)
            raise RenameError(e, oldpath, newpath)
    try:
        os.rename(oldpath, newpath)
        return True
    except EnvironmentError as e:
        try:
            shutil.move(oldpath, newpath)
            return True
        except EnvironmentError as e:
            raise RenameError(e, oldpath, newpath)


def rename_dir(filename, olddir, newdir):
    if newdir == olddir:
        return False
    try:
        os.renames(olddir, newdir)
        return True
    except EnvironmentError as e:
        if issubfolder(olddir, newdir, None):
            e.strerror = translate('Errors',
                                   "Cannot move directory to a subdirectory within itself.")
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
            del (d[key])
    return d


def equal(audio1, audio2, tags=('artist', 'album', 'title')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if to_string(audio1[key]) != to_string(audio2[key]):
                return False
        else:
            return False
    return True


def fields_from_text(text):
    if not text:
        return []
    return [_f for _f in map(str.strip, text.split(',')) if _f]


def matching(audios, listing):
    ret = {}
    for audio in audios:
        for tag in listing:
            if equal(audio, tag):
                ret[audio] = tag
    if len(audios) == len(ret):
        return ret, True
    return ret, False


def m_to_string(v):
    if isempty(v):
        return escape_html(BLANK)
    elif isinstance(v, str):
        return escape_html(v)
    elif isinstance(v, bytes):
        return escape_html(v.decode('utf8', 'replace'))
    else:
        return escape_html(SEPARATOR.join(v))


def pprint_tag(tags, fmt="<b>%s</b>: %s<br />", show_read_only=False):
    image_tr = translate('Defaults', '%s images')
    if tags:
        if isinstance(tags, str):
            return tags
        elif not hasattr(tags, 'items'):
            return SEPARATOR.join([x for x in tags if x is not None])

        if show_read_only:
            items = ((k, v) for k, v in tags.items() if k != '__image')
        else:
            items = ((k, v) for k, v in tags.items() if
                     k not in READONLY and k != '__image')

        map_func = lambda v: fmt % (v[0], m_to_string(v[1]))

        items = sorted(items, key=itemgetter(0))

        if '__image' in tags:
            items.insert(0, ('__image', image_tr % len(tags['__image'])))

        return "".join(map(map_func, items))


def rename_file(audio, tags):
    """If tags(a dictionary) contains a PATH key, then the file
    in self.taginfo[row] is renamed based on that.

    If successful, tags is returned(with the new filename as a key)
    otherwise {} is returned."""
    test_audio = MockTag()
    test_audio.filepath = audio.filepath
    renamed = False

    if PATH in tags:
        test_audio.filepath = to_string(tags[PATH])
    if FILENAME in tags:
        test_audio.filename = safe_name(to_string(tags[FILENAME]))
    if EXTENSION in tags:
        test_audio.ext = safe_name(to_string(tags[EXTENSION]))

    if DIRNAME in tags:
        newdir = safe_name(encode_fn(tags[DIRNAME]))
        newdir = os.path.join(os.path.dirname(audio.dirpath),
                              newdir)
        if rename_dir(audio.filepath, audio.dirpath, newdir):
            audio.dirpath = newdir
            test_audio.dirpath = newdir
            renamed = True
    elif DIRPATH in tags:
        newdir = encode_fn(to_string(tags[DIRPATH]))
        if rename_dir(audio.filepath, audio.dirpath, newdir):
            audio.dirpath = newdir
            renamed = True
            test_audio.dirpath = newdir

    if rename(audio.filepath, test_audio.filepath):
        audio.filepath = test_audio.filepath
        renamed = True

    return renamed


def split_by_tag(tracks, main='artist', secondary='album'):
    def get(t, f):
        return to_string(t.get(f)).strip()

    if secondary:
        ret = defaultdict(lambda: defaultdict(lambda: []))
        [ret[get(track, main)]
         [get(track, secondary)].append(track) for track in tracks]
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
        main_val = to_string(track.get(field)).strip()
        if main_val in indexes:
            ret[indexes[main_val]][1].append(track)
        else:
            index = len(ret)
            indexes[main_val] = index
            ret.append([main_val, [track]])
    return ret


def to_list(value):
    if isinstance(value, (str, int, int, float)):
        value = [str(value)]
    elif isinstance(value, str):
        value = [value]
    return value


def to_string(value):
    if isempty(value):
        return ''
    elif isinstance(value, bytes):
        return value.decode('utf8')
    elif isinstance(value, str):
        return value
    elif isinstance(value, (float, int, int)):
        return str(value)
    else:
        return to_string(value[0])


def write(audio, tags, save_mtime=True, justrename=False):
    """A function to update one row.
    row is the row, tags is a dictionary of tags.

    If undo`is True, then an undo level is created for this file.
    If justrename is True, then (if tags contain a PATH or EXTENSION key)
    the file is just renamed i.e not tags are written.
    """
    tags = deepcopy(tags)
    renamed = False
    if audio.library and (ARTIST in tags or ALBUM in tags):
        artist = audio.get(ARTIST, '')
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
                  tags.get(field, '') != audio.get(field, ''))])

    if '__image' in tags:
        if not audio.IMAGETAGS:
            del (tags['__image'])
        else:
            undo['__image'] = audio.images

    try:
        if fn_fields:
            for key in fn_fields:
                if key in fn_hash:
                    undo[key] = getattr(audio, fn_hash[key])
            renamed = rename_file(audio, fn_fields)

        if not justrename:
            user_only = dict_diff(audio, without_file(tags))
            if user_only:
                audio.update(user_only)
                audio.save()
            elif not user_only and not renamed:
                return {}
    except EnvironmentError:
        audio.update(undo)
        audio.preview = preview
        raise
    
    except MutagenError as e:
        if isinstance(e.args[0], PermissionError):
            audio.update(undo)
            logging.exception(e)
            raise e.args[0]
        else:
            raise

    try:
        if save_mtime:
            setmodtime(audio.filepath, audio.accessed, audio.modified)
        else:
            os.utime(audio.dirpath, None)
    except EnvironmentError as ex:
        logging.error("Could not set modification time for file or directory.")
        logging.exception(ex)
    return undo


def dict_diff(d1, d2):
    """Compute difference between d2 and d1, returns dict with
    k,v in d2 if d2[k] != d1[k].

    For values, the string "this here" will be considered the same as the list
    ["this here"].
    """
    ret = {}
    for key in d2:
        try:
            if key not in d1:
                ret[key] = d2[key]
            else:
                if to_list(d2[key]) != to_list(d1[key]):
                    ret[key] = d2[key]
        except (TypeError, ValueError):
            ret[key] = d2[key]
    return ret


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
        self.__code__ = function.__code__
        self.print_string = pprint
        self.desc = desc
        self.args = args
        if not args:
            return
        newargs = []
        for arg in args:
            arg = list(arg)
            if arg[1] == constants.CHECKBOX:
                arg[2] = str(bool(arg[2]))
            newargs.append(arg)
        self.args = newargs

    def __call__(self, *args):
        return self.function(*args)
