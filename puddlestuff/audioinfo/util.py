import base64
import calendar
import imghdr
import logging
import os
import sys
import time
from copy import deepcopy
from decimal import Decimal
from errno import ENOENT
from os import path, stat

import mutagen

from .constants import *

try:
    from .. import version_string

    app_name = 'puddletag v%s' % version_string
except ImportError:
    app_name = 'puddletag'

from stat import ST_SIZE, ST_MTIME, ST_CTIME, ST_ATIME

FS_ENC = sys.getfilesystemencoding()

fn_hash = {
    PATH: 'filepath',
    FILENAME: 'filename',
    EXTENSION: 'ext',
    DIRPATH: 'dirpath',
    DIRNAME: 'dirname',
    FILENAME_NO_EXT: 'filename_no_ext',
    PARENT_DIR: 'parent_dir'}

splitext = lambda x: path.splitext(x)[1][1:].lower()


def b64_to_img(img):
    ret = img.copy()
    ret['data'] = base64.b64decode(img['data'].encode('ascii'))
    return ret


def commonimages(images):
    """Checks the equality of the list of images.

    Returns:
        0 if some of the images aren't equal.
        None, if an empty list was passed.
        the first image in the list if all of them are equal.
    """

    if images:
        x = images[0]
    else:
        x = None
    for image in images[1:]:
        if image != x:
            return 0
    if not x:
        return None
    return x


def commontags(audios):
    """Checks the list of audios for common values.

    audios is a list of Tag objects.

    Returns a 3-tuple:
        combined - A dictionary containing all the fields found
        in audios as keys and the first value corresponding
        to that key found.
        
        Another dictionary with the same keys as combined.
        For each key, the value is the number of items
        found in audios that have exactly the same value
        combined[key].

        A list containing the union of all the image keys found.
    """
    images = []
    combined = {}
    tags = {}
    images = []
    imagetags = set()

    for audio in audios:
        if getattr(audio, 'IMAGETAGS', []):
            image = audio[IMAGE_FIELD] if audio[IMAGE_FIELD] else []
            imagetags = imagetags.union(audio.IMAGETAGS)
        else:
            image = []
        images.append(image)

        if hasattr(audio, 'usertags'):
            audio = audio.usertags
        else:
            audio = usertags(audio)

        for field, value in audio.items():
            value = list(value) if not isinstance(value, str) else [value]
            if field in combined:
                if combined[field] == value:
                    tags[field] += 1
                else:
                    values = combined[field]
                    [values.append(v) for v in value if v not in values]
            else:
                combined[field] = value
                tags[field] = 1
    combined['__image'] = commonimages(images)
    return combined, tags, imagetags


def converttag(tag):
    """Converts each value in tag to a list if the key doesn't begin with __."""
    return dict((k, unicode_list(v)) if not k.startswith('__') else (k, v)
                for k, v in tag.items())


def cover_info(images, d=None):
    """Finds cover metadata in images.

    Returns dictionary:
        {__num_images: unicode(len(images)) else '0'
        __image_mimetype: mimetype of images[0]
        __image_type: type of images[0]}

    if d is supplied, it'll be updated with the returned
        dictionary.
    """
    info = {}
    if not images:
        info[NUM_IMAGES] = '0'
        info[IMAGE_MIMETYPE] = ''
    else:
        info[NUM_IMAGES] = str(len(images))
        image = images[0]
        if MIMETYPE in image:
            info[IMAGE_MIMETYPE] = image[MIMETYPE]
        else:
            info[IMAGE_MIMETYPE] = get_mime(image[DATA])

        if IMAGETYPE in image:
            try:
                info[IMAGE_TYPE_FIELD] = IMAGETYPES[image[IMAGETYPE]]
            except IndexError:
                info[IMAGE_TYPE_FIELD] = IMAGETYPES[DEFAULT_COVER]

    if d:
        if not info[IMAGE_MIMETYPE]:
            del (info[IMAGE_MIMETYPE])
            try:
                del (d[IMAGE_MIMETYPE])
            except KeyError:
                pass
        d.update(info)
    return info


def decode_fn(filename, errors='replace'):
    """Decodes a filename from the filesystem encoding."""
    if isinstance(filename, str):
        return filename
    else:
        return filename.decode(FS_ENC, errors)


def del_deco(func):
    """Decorates __delitem__ methods of Tag objects using their mapping.

    If the object has a mapping set, the mapped field
    will be passed to object.__delitem__ so that it can behave
    without regard to mappings."""

    def f(self, key):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key])
        return func(self, key)

    return f


def encode_fn(filename):
    """Encode a filename to filesystem encoding."""
    if isinstance(filename, str):
        return filename
    else:
        return filename.encode(FS_ENC)


def getdeco(func):
    """Decorates __getitem__ methods of Tag objects using their mapping

    If the object has a mapping set, the mapped field
    will be passed to object.__getitem__ so that __getitem__ can behave
    without regard to mappings."""

    def f(self, key):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key])
        return func(self, key)

    return f


def getfilename(filename):
    """Returns the full path of filename."""
    return path.abspath(filename)


def getinfo(filename):
    """Gets file info like file-size etc. from filename.

    Returns a dictionary keys, values as puddletag
    wants it.
    """

    get_time = lambda f, s: time.strftime(f, time.gmtime(s))
    fileinfo = stat(filename)
    size = fileinfo[ST_SIZE]
    accessed = fileinfo[ST_ATIME]
    modified = fileinfo[ST_MTIME]
    created = fileinfo[ST_CTIME]
    return ({
        "__size": str(size),
        '__file_size': str_filesize(size),
        '__file_size_bytes': str(size),
        '__file_size_kb': '%d KB' % int(size / 1024),
        '__file_size_mb': '%.2f MB' % (size / 1024.0 ** 2),

        "__created": strtime(created),
        '__file_create_date': get_time('%Y-%m-%d', created),
        '__file_create_datetime':
            get_time('%Y-%m-%d %H:%M:%S', created),
        '__file_create_datetime_raw': str(created),

        "__modified": strtime(modified),
        '__file_mod_date': get_time('%Y-%m-%d', modified),
        '__file_mod_datetime':
            get_time('%Y-%m-%d %H:%M:%S', modified),
        '__file_mod_datetime_raw': str(modified),

        '__accessed': strtime(accessed),
        '__file_access_date': get_time('%Y-%m-%d', accessed),
        '__file_access_datetime':
            get_time('%Y-%m-%d %H:%M:%S', accessed),
        '__file_access_datetime_raw': str(accessed),

        '__app': app_name,

    })


def get_mime(data):
    """Retrieve the mimetype of the image, data (a bytestring).

    Returns either 'image/jpeg', 'image/png' or ''."""
    mime = imghdr.what(None, data)
    if mime:
        return 'image/' + mime
    else:
        return ''


def get_total(tag):
    """If tag['track'] is of format x/y returns, y."""
    value = to_string(tag['track'])
    try:
        return value.split('/')[1].strip()
    except IndexError:
        raise KeyError('__total')


def img_to_b64(img):
    ret = img.copy()
    ret['data'] = base64.b64encode(img['data']).decode('ascii')
    return ret


def info_to_dict(info):
    """Create a dictionary representation of info's attributes.

    Converts recognized properties from info to puddletag equivalent.
    Ef. info.channels will become '__channels' in the returned
    dictionary. Info.length becomes '__length' and so on.
    """
    attrs = dir(info)
    tags = {}
    try:
        tags["__frequency"] = strfrequency(info.sample_rate)
        tags["__frequency_num"] = info.sample_rate / 1000.0
    except AttributeError:
        pass

    try:
        tags["__length"] = strlength(info.length)
    except AttributeError:
        pass

    try:
        tags["__length_seconds"] = str(int(info.length))
    except AttributeError:
        pass

    try:
        tags["__bitrate"] = strbitrate(info.bitrate)
        tags["__bitrate_num"] = str(int(info.bitrate / 1000))
    except AttributeError:
        tags["__bitrate"] = '0 kb/s'
        tags["__bitrate_num"] = 0

    try:
        tags['__bitspersample'] = str(info.bits_per_sample)
    except AttributeError:
        pass

    try:
        tags['__channels'] = str(info.channels)
    except AttributeError:
        pass

    try:
        tags['__layer'] = str(info.layer)
    except AttributeError:
        pass

    if isinstance(info, mutagen.mp3.MPEGInfo):
        try:
            tags['__mode'] = MODES[info.mode]
        except AttributeError:
            pass
    else:
        try:
            tags['__mode'] = MONO if info.channels == 1 else STEREO
        except AttributeError:
            pass

    try:
        tags['__titlegain'] = str(info.title_gain)
    except AttributeError:
        pass

    try:
        tags['__albumgain'] = str(info.album_gain)
    except AttributeError:
        pass

    try:
        tags['__version'] = str(info.version)
    except AttributeError:
        pass

    try:
        tags['__md5sig'] = str(info.md5_signature)
    except AttributeError:
        pass

    return tags


def isempty(value):
    """Check if value is empty.

    Empty means:
        The value evaluates to False and as not a number.
        All of value's members are False. eg

    >>>isempty('')
    True
    >>>isempty(['', None])
    True
    >>>isempty([0])
    False
    """
    if isinstance(value, int):
        return False
    if not value:
        return True
    try:
        return not [z for z in value if z or isinstance(z, int)]
    except TypeError:
        return False


def keys_deco(func):
    """Decorates the keys method of Tag objects using their mapping

    Maps the list keys returned by the object.keys using object.mapping
    and object.revmapping.
    """

    def f(self):
        if not self.revmapping:
            return func(self)
        else:
            mapping = self.mapping
            revmapping = self.revmapping
            return [mapping.get(k, k) for k in func(self)
                    if not (k in revmapping and k not in mapping)]

    return f


def lngfrequency(value):
    """Converts the string 'x kHz' to x Hz (returned as long)."""
    return int(Decimal(value.split(" ")[0]) * 1000)


def lnglength(value):
    """Converts a string representation of length to seconds.

    length can be in HH:MM:SS or MM:SS format."""
    if len(value.split(':')) == 3:
        (hours, minutes, seconds) = list(map(float, value.split(':')))
        (hours, minutes, seconds) = (int(hours), int(minutes), int(seconds))
        return (hours * 3600) + (minutes * 60) + seconds
    else:
        (minutes, seconds) = list(map(float, value.split(':')))
        (minutes, seconds) = (int(minutes), int(seconds))
        return (minutes * 60) + seconds


def lngtime(value):
    '''Converts time in %Y-%m-%d %H:%M:%S format to seconds.'''
    return calendar.timegm(time.strptime(value, '%Y-%m-%d %H:%M:%S'))


def path_to_string(value):
    """Convert the path to a bytestring."""
    if not value:
        return ''
    elif isinstance(value, str):
        return encode_fn(value)
    else:
        return path_to_string(value[0])


_image_defaults = {
    DESCRIPTION: lambda i: i.get(DESCRIPTION, ''),
    MIMETYPE: lambda i: get_mime(i[DATA]) if MIMETYPE in i else \
        get_mime(i[DATA]),
    IMAGETYPE: lambda i: i.get(IMAGETYPE, DEFAULT_COVER),
    DATA: lambda i: i[DATA]}


def parse_image(image, keys=None):
    """Get default values for the image if they don't exist."""
    if keys is None:
        keys = [DATA, MIMETYPE, DESCRIPTION, IMAGETYPE]
    return dict((k, _image_defaults[k](image)) for k in keys)


def reversedict(d):
    return dict((v, k) for k, v in d.items())


def setdeco(func):
    """Decorates the __setitem__ method of a Tag object using it's mapping.

    If the object has a mapping set, the mapped field
    will be passed to object.__setitem__ so that it can behave
    without regard to mappings."""

    def f(self, key, value):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key], value)
        elif key in self.mapping:
            return
        return func(self, key, value)

    return f


def setmodtime(fn, atime, mtime):
    '''Sets the access and modification times of fn.

    atime and mtime should both be in "%Y-%m-%d %H:%M:%S" format.'''
    mtime = lngtime(mtime)
    atime = lngtime(atime)
    os.utime(fn, (atime, mtime))


def set_total(tag, value):
    """If tag['track'] is of format x/y set's y to value."""
    track = to_string(tag['track']).split('/', 1)

    if isempty(value) and track:
        tag['track'] = track[0]
        return

    value = to_string(value)
    if not (value and track):
        return False
    tag['track'] = track[0] + '/' + value
    return True


def strbitrate(bitrate):
    """Converts the bitrate in bits/s to a string in kb/s."""
    return str(bitrate / 1000) + ' kb/s'


_sizes = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}


def str_filesize(size):
    """Convert size in bytes to it's string representation and returns it.

    >>>str_filesize(1024)
    '1 KB'
    >>>str_filesize(88)
    '88 B'
    >>>str_filesize(1024**3)
    '1.00 GB'
    """
    valid = [z for z in _sizes if size / (1024.0 ** z) > 1]
    val = max(valid)
    if val < 2:
        return '%d %s' % (size / (1024 ** val), _sizes[val])
    else:
        return '%.2f %s' % (size / (1024.0 ** val), _sizes[val])


def strfrequency(value):
    """Converts the frequency Hz to a string in kHz."""
    return "%.1f kHz" % (value / 1000.0)


def stringtags(tag, leaveNone=False):
    """Converts each value in tag to a string.

    A dictionary, with keys as found in tag.
    If a value's already a string, it's returned as is,
    otherwise the first item of the list is used.

    leaveNone = False will remove any values
    considered empty from being part of the returned dictionary.
    eg. '', [''], None.
    Otherwise, they're returned as ''    
    """

    newtag = {}
    for i in tag:
        v = tag[i]
        if i in INFOTAGS:
            newtag[i] = v
            continue
        if isinstance(i, (int, int, float)) or hasattr(v, 'items'):
            continue

        if leaveNone and isempty(v):
            newtag[i] = ''
            continue
        elif (not v) or (hasattr(v, '__iter__') and len(v) == 1 and not v[0]):
            continue

        if isinstance(v, str):
            newtag[i] = v
        elif isinstance(v, (int, float)):
            newtag[i] = str(v)
        elif isinstance(i, str) and not isinstance(v, str):
            newtag[i] = v[0]
        else:
            newtag[i] = v
    return newtag


def strlength(value):
    """Converts the value in seconds to HH:MM:SS format.

    If HH = 00: returns the value in MM:SS format"""
    seconds = value % 60
    minutes = (value % 3600) // 60
    hours = value // 3600
    if hours > 0:
        return '%02d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%02d:%02d' % (minutes, seconds)


def strtime(seconds):
    """Converts UNIX time(in seconds) to more Human Readable format."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))


def tag_to_json(audio, fields=None):
    from .. import audioinfo
    if isinstance(audio, str):
        try:
            audio = audioinfo.Tag(audio)
        except:
            logging.exception("Invalid File: " + audio)
            return

    if audio is None:
        return
    try:
        if fields:
            tags = dict((k, audio[k]) for k in fields if k in audio)
        else:
            fields = []
            tags = audio.tags.copy()
    except AttributeError:
        tags = audio.copy()

    try:
        if not fields or '__image' in fields:
            if audio.images:
                tags['__image'] = list(map(img_to_b64, audio.images))
            elif '__image' in tags:
                tags['__image'] = list(map(img_to_b64, tags['__image']))
    except AttributeError:
        if not fields or '__image' in fields:
            if '__image' in tags:
                tags['__image'] = list(map(img_to_b64, tags['__image']))

    return tags


def to_string(value, errors='strict'):
    """Convert the value to a unicode string.

    If it's a list, the first index is used."""
    if not value:
        return ''
    elif isinstance(value, str):
        return value
    elif isinstance(value, int):
        return str(value)
    else:
        return to_string(value[0])


def usertags(tag):
    """Return dictionary of all editable key, value pairs found in tag."""
    ret = dict((z, v) for z, v in tag.items() if isinstance(z, str)
               and not z.startswith('__'))
    return ret


def unicode_list(value):
    """Modifies the passed value to a unicode list.

    >>>unicode_list("value")
    ['value']
    >>>unicode_list(['value1', 'value2']
    ['value1', 'value2']
    """
    if not value:
        return []
    if isinstance(value, str):
        return [str(value)]
    elif isinstance(value, str):
        return [str(value, 'utf8', 'replace')]
    elif isinstance(value, int):
        return [str(value)]
    else:
        return [to_string(v, 'replace') for v in value if v]


def writeable(tags):
    return [z for z in tags if not z.starswith('__') or z.startswith('~')]


class CaselessDict(dict):
    """Caseless dictionry. Only accepts strings as keys."""

    def __init__(self, other=None):
        self._keys = {}
        dict.__init__(self)
        if other:
            # Doesn't do keyword args
            if isinstance(other, dict):
                for k, v in other.items():
                    self[k] = v
            else:
                for k, v in other:
                    self[k] = v

    def __contains__(self, key):
        return key.lower() in self._keys

    def __deepcopy__(self, memo):
        cls = CaselessDict()
        for key, value in self.items():
            cls[key] = deepcopy(value)
        return cls

    def __delitem__(self, key):
        dict.__delitem__(self, self._keys[key.lower()])
        del (self._keys[key.lower()])

    def __getitem__(self, key):
        return dict.__getitem__(self, self._keys[key.lower()])

    def __setitem__(self, key, value):
        low = key.lower()
        dict.__setitem__(self, key, value)
        if self._keys.get(low, key) != key:
            dict.__delitem__(self, self._keys[low])
        self._keys[low] = key

    def fromkeys(self, iterable, value=None):
        d = CaselessDict()
        for k in iterable:
            d[k] = value
        return d

    def get(self, key, def_val=None):
        if key in self:
            return self[key]
        else:
            return def_val

    def has_key(self, key):
        return key.lower() in self._keys

    def update(self, other):
        for k, v in other.items():
            self[k] = v


class MockTag(object):
    """Use as base for all tag classes."""

    def __init__(self, filename=None):
        object.__init__(self)
        self._info = {}
        self.__filepath = ''
        if filename:
            self.link(filename)

    def get_filepath(self):
        return self.__filepath

    def set_filepath(self, val):
        self.__filepath = path_to_string(val)
        val = to_string(val, 'replace')

        if hasattr(self, 'mut_obj'):
            self.mut_obj.filename = self.__filepath
        ret = {
            PATH: val,
            DIRPATH: path.dirname(val),
            FILENAME: path.basename(val)}

        ret[FILENAME_NO_EXT], ret[EXTENSION] = path.splitext(ret[FILENAME])
        ret[EXTENSION] = ret[EXTENSION][1:]
        ret[DIRNAME] = path.basename(ret[DIRPATH])
        ret[PARENT_DIR] = path.basename(path.dirname(ret[DIRPATH]))

        return ret

    def _set_ext(self, val):
        if val:
            val = path_to_string(val)
            self.filepath = '%s%s%s' % (path.splitext(self.filepath)[0],
                                        path.extsep, val)
        else:
            self.filepath = path.splitext(self.filepath)[0]

    def _get_ext(self):
        return path.splitext(self.filepath)[1][1:]

    def _get_filename(self):
        return path.basename(self.filepath)

    def _set_filename(self, val):
        val = path_to_string(val)
        self.filepath = path.join(self.dirpath, val)

    def _get_dirpath(self):
        return path.dirname(self.filepath)

    def _set_dirpath(self, val):
        val = path_to_string(val)
        self.filepath = path.join(val, self.filename)

    def _get_dirname(self):
        return path.basename(self.dirpath)

    def _set_dirname(self, value):
        value = path_to_string(value)
        self.dirpath = path.join(path.dirname(self.dirpath), value)

    def _set_filename_no_ext(self, value):
        self.filename = value + '.' + self.ext

    def _get_filename_no_ext(self):
        return path.splitext(path.basename(self.filepath))[0]

    def _get_parent_dir(self):
        return path.basename(path.dirname(self.dirpath))

    def _set_parent_dir(self, value):
        self.dirpath = path.join(path.dirname(self.dirpath), value)

    filepath = property(get_filepath, set_filepath)
    dirpath = property(_get_dirpath, _set_dirpath)
    dirname = property(_get_dirname, _set_dirname)
    ext = property(_get_ext, _set_ext)
    filename = property(_get_filename, _set_filename)
    filename_no_ext = property(_get_filename_no_ext, _set_filename_no_ext)
    parent_dir = property(_get_parent_dir, _set_parent_dir)
    tags = property(lambda self: dict(list(self.items())))
    usertags = property(lambda self: usertags(self))

    def __iter__(self):
        return list(self.keys()).__iter__()

    def __len__(self):
        return len(self.usertags)

    def clear(self):
        for key in self.usertags:
            del (self[key])

    def get(self, key, default=None):
        return self[key] if key in self else default

    def items(self):
        return [(key, self[key]) for key in self]

    def iteritems(self):
        return ((key, self[key]) for key in self)

    def load(self, filename, filetype=None):
        filename = getfilename(filename)
        self.filepath = filename
        if filetype is not None:
            audio = filetype(filename)
        else:
            audio = None
        tags = getinfo(filename)
        return tags, audio

    def real(self, key):
        if key in self.revmapping:
            return self.revmapping[key]
        return key

    def save(self):
        if not path.exists(self.filepath):
            raise IOError(ENOENT, os.strerror(ENOENT), self.filepath)

    def set_attrs(self, attrs, tags=None):
        if tags is None:
            tags = self
        [setattr(self, z, tags['__%s' % z]) for z in attrs if
         '__%s' % z in tags]

    def stringtags(self):
        return stringtags(self)

    def update(self, dictionary=None, **kwargs):
        if dictionary is None:
            return
        if hasattr(dictionary, 'items'):
            for key, value in dictionary.items():
                self[key] = value
        else:
            for key, value in dictionary:
                self[key] = value

    def values(self):
        return [self[key] for key in self]
