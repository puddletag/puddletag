## -*- coding: utf-8 -*-

import mutagen, time, pdb, calendar, os, logging, sys, imghdr
from errno import ENOENT
from decimal import Decimal
from copy import copy, deepcopy
from os import path, stat

from stat import ST_SIZE, ST_MTIME, ST_CTIME, ST_ATIME

PATH = u"__path"
FILENAME = u"__filename"
EXTENSION = '__ext'
DIRPATH = '__dirpath'
DIRNAME = '__dirname'
FILENAME_NO_EXT = '__filename_no_ext'
PARENT_DIR = '__parent_dir'

NUM_IMAGES = '__num_images'
IMAGE_MIMETYPE = '__image_mimetype'

READONLY = ('__bitrate', '__frequency', "__length", "__modified",
            "__size", "__created", "__library", '__accessed', '__filetype',
            '__channels', '__version', '__titlegain', '__albumgain',
            NUM_IMAGES, IMAGE_MIMETYPE, "__cover_mimetype", "__cover_size",
            "__covers", "__file_create_date", "__file_create_datetime",
            "__file_create_datetime_raw", "__file_mod_date",
            "__file_mod_datetime", "__file_mod_datetime_raw",
            "__file_size", "__file_size_bytes", "__file_size_kb",
            "__file_size_mb", "__length_seconds",
            "__mode", "__parent_dir", "__tag", "__tag_read", "__total",
            '__file_access_date', '__file_access_datetime',
            '__file_access_datetime_raw', '__layer')
IMAGES = '__image'
FILETAGS = [PATH, FILENAME, EXTENSION, DIRPATH, DIRNAME, FILENAME_NO_EXT,
    PARENT_DIR]
INFOTAGS = FILETAGS + list(READONLY)

fn_hash = {
    PATH: 'filepath',
    FILENAME:'filename',
    EXTENSION: 'ext',
    DIRPATH: 'dirpath',
    DIRNAME: 'dirname',
    FILENAME_NO_EXT: 'filename_no_ext',
    PARENT_DIR: 'parent_dir'}

MIMETYPE = 'mime'
DESCRIPTION = 'description'
DATA = 'data'
IMAGETYPE = 'imagetype'

IMAGETAGS = (MIMETYPE, DESCRIPTION, DATA, IMAGETYPE)

MONO = u'Mono'
JOINT_STEREO = u'Joint-Stereo'
DUAL_CHANNEL = u'Dual-Channel'
STEREO = u'Stereo'
MODES = [STEREO, JOINT_STEREO, DUAL_CHANNEL, MONO]

TAGS = {'TALB': 'album',
        'TBPM': 'bpm',
        'TCOM': 'composer',
        'TCON': 'genre',
        'TCOP': 'copyright',
        'TDEN': 'encodingtime',
        'TDLY': 'playlistdelay',
        'TDOR': 'originaldate',
        'TDRC': 'year',
        'TDRL': 'releasetime',
        'TDTG': 'taggingtime',
        'TENC': 'encodedby',
        'TEXT': 'lyricist',
        'TFLT': 'filetype',
        'TIT1': 'grouping',
        'TIT2': 'title',
        'TIT3': 'version',
        'TKEY': 'initialkey',
        'TLAN': 'language',
        'TLEN': 'length',
        'TMED': 'mediatype',
        'TMOO': 'mood',
        'TOAL': 'originalalbum',
        'TOFN': 'originalfilename',
        'TOLY': 'author',
        'TOPE': 'originalartist',
        'TOWN': 'fileowner',
        'TPE1': 'artist',
        'TPE2': 'performer',
        'TPE3': 'conductor',
        'TPE4': 'arranger',
        'TPOS': 'discnumber',
        'TPRO': 'producednotice',
        'TPUB': 'organization',
        'TRCK': 'track',
        'TRSN': 'radiostationname',
        'TRSO': 'radioowener',
        'TSOA': 'albumsortorder',
        'TSOP': 'performersortorder',
        'TSOT': 'titlesortorder',
        'TSRC': 'isrc',
        'TSSE': 'encodingsettings',
        'TSST': 'setsubtitle'}
REVTAGS = dict([reversed(z) for z in TAGS.items()])


IMAGETYPES = ['Other', 'File Icon', 'Other File Icon', 'Cover (front)',
    'Cover (back)', 'Leaflet page', 'Media (e.g. label side of CD)',
    'Lead artist', 'Artist', 'Conductor', 'Band', 'Composer','Lyricist',
    'Recording Location', 'During recording', 'During performance',
    'Movie/video screen capture', 'A bright coloured fish', 'Illustration',
    'Band/artist logotype', 'Publisher/Studio logotype']

splitext = lambda x: path.splitext(x)[1][1:].lower()

def setmodtime(filepath, atime, mtime):
    mtime = lngtime(mtime)
    atime = lngtime(atime)
    os.utime(filepath, (atime, mtime))

def commonimages(imagedicts):
    if imagedicts:
        x = imagedicts[0]
    else:
        x = None
    for image in imagedicts[1:]:
        if image != x:
            return 0
    if not x:
        return None
    return x

def commontags(audios):
    images = []
    combined = {}
    tags = {}
    images = []
    imagetags = set()
    for audio in audios:
        if audio.IMAGETAGS:
            image = audio[IMAGES] if audio[IMAGES] else []
        else:
            image = []
        images.append(image)
        imagetags = imagetags.union(audio.IMAGETAGS)
        audio = audio.usertags

        for field, value in audio.items():
            if field in combined:
                if combined[field] == value:
                    tags[field] += 1
            else:
                combined[field] = value
                tags[field] = 1
    combined[IMAGES] = commonimages(images)
    return combined, tags, imagetags


FS_ENC = sys.getfilesystemencoding()
def encode_fn(filename):
    if isinstance(filename, str):
        return filename
    else:
        return filename.encode(FS_ENC)

def decode_fn(filename, errors='replace'):
    if isinstance(filename, unicode):
        return filename
    else:
        return filename.decode(FS_ENC, errors)

def unicode_list(value):
    if not value:
        return []
    if isinstance(value, unicode):
        return [unicode(value)]
    elif isinstance(value, str):
        return [unicode(value, 'utf8', 'replace')]
    elif isinstance(value, (int, long)):
        return [unicode(value)]
    else:
        return [to_string(v, 'replace') for v in value if v]

def info_to_dict(info):
    tags = {}
    try: tags["__frequency"] = strfrequency(info.sample_rate)
    except AttributeError: pass

    try: tags["__length"] = strlength(info.length)
    except AttributeError: pass

    try: tags["__length_seconds"] = unicode(int(info.length))
    except AttributeError: pass

    try: tags["__bitrate"] = strbitrate(info.bitrate)
    except AttributeError: tags[u"__bitrate"] = u'0 kb/s'

    try: tags['__bitspersample'] = unicode(info.bits_per_sample)
    except AttributeError: pass

    try: tags['__channels'] = unicode(info.channels)
    except AttributeError: pass

    try: tags['__layer'] = unicode(info.layer)
    except AttributeError: pass

    if isinstance(info, mutagen.mp3.MPEGInfo):
        try: tags['__mode'] = MODES[info.mode]
        except AttributeError: pass
    else:
        try: tags['__mode'] = MONO if info.channels == 1 else STEREO
        except AttributeError: pass

    try: tags['__titlegain'] = unicode(info.title_gain)
    except AttributeError: pass


    try: tags['__albumgain'] = unicode(info.album_gain)
    except AttributeError: pass

    try: tags['__version'] = unicode(info.version)
    except AttributeError: pass

    return tags

def stringtags(tag, leaveNone = False):
    """Takes a dictionary(tag) and returns string representations of each key.
    If a key is a list then the first item of that list is returned."""

    #Created this function, because a lot of puddletag's functions expects dicts with
    #only string items. So, rather than rewriting every function to do something like this, I use this.
    newtag = {}
    for i in tag:
        v = tag[i]
        if i in INFOTAGS:
            newtag[i] = v
            continue
        if isinstance(i, int) or hasattr(v, 'items'):
            continue

        if leaveNone and ((not v) or (len(v) == 1 and not v[0])):
            newtag[i] = u''
            continue
        elif (not v) or (len(v) == 1 and not v[0]):
            continue

        if isinstance(v, basestring):
            newtag[i] = v
        elif isinstance(i, basestring) and not isinstance(v, basestring):
            newtag[i] = v[0]
        else:
            newtag[i] = v
    return newtag

def strlength(value):
    """Converts seconds to length in minute:seconds format."""
    seconds = long(value % 60)
    if seconds < 10:
        seconds = u"0" + unicode(seconds)
    if value/3600 >= 1:
        return '%d:%d:%s' % (long(value/3600), long(value % 3600 / 60), unicode(seconds))
    else:
        return "".join([unicode(long(value/60)),  ":", unicode(seconds)])

def strbitrate(bitrate):
    """Returns a string representation of bitrate in kb/s."""
    return unicode(bitrate/1000) + u' kb/s'

def strfrequency(value):
    return unicode(value / 1000.0)[:4] + u" kHz"

def lnglength(value):
    """Converts a string representation of length to seconds."""
    if len(value.split(':')) == 3:
        (hours, minutes, seconds) = value.split(':')
        (hours, minutes, seconds) = (long(hours), long(minutes), long(seconds))
        return (hours * 3600) + (minutes * 60) + seconds
    else:
        (minutes, seconds) = value.split(':')
        (minutes, seconds) = (long(minutes), long(seconds))
        return (minutes * 60) + seconds

def lngfrequency(value):
    """Inverse of strfrequency."""
    return long(Decimal(value.split(" ")[0]) * 1000)

def strtime(seconds):
    """Converts UNIX time(in seconds) to more Human Readable format."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))

def lngtime(value):
    '''Converts time in %Y-%m-%d %H:%M:%S format to seconds.'''
    return calendar.timegm(time.strptime(value, '%Y-%m-%d %H:%M:%S'))

def getfilename(filename):
    return path.realpath(filename)

def getinfo(filename):
    get_time = lambda f, s: time.strftime(f, time.gmtime(s))
    fileinfo = stat(filename)
    size = fileinfo[ST_SIZE]
    accessed = fileinfo[ST_ATIME]
    modified = fileinfo[ST_MTIME]
    created = fileinfo[ST_CTIME]
    return ({
        "__size" : unicode(size),
        '__file_size': str_filesize(size),
        '__file_size_bytes': unicode(size),
        '__file_size_kb': u'%d KB' % (size / 1024),
        '__file_size_mb': u'%d KB' % (size / 1024**2),

        "__created": strtime(created),
        '__file_create_date': get_time('%Y-%m-%d', created),
        '__file_create_datetime':
            get_time('%Y-%m-%d %H:%M:%S', created),
        '__file_create_datetime_raw': unicode(created),

        "__modified": strtime(modified),
        '__file_mod_date': get_time('%Y-%m-%d', modified),
        '__file_mod_datetime':
            get_time('%Y-%m-%d %H:%M:%S', modified),
        '__file_mod_datetime_raw': unicode(modified),

        '__accessed': strtime(accessed),
        '__file_access_date': get_time('%Y-%m-%d', accessed),
        '__file_access_datetime':
            get_time('%Y-%m-%d %H:%M:%S', accessed),
        '__file_access_datetime_raw': unicode(accessed),

        })

def converttag(tags):
    for tag,value in tags.items():
        if (tag not in INFOTAGS) and (isinstance(value, (basestring, int, long))):
            tags[tag] = [value]
        else:
            tags[tag] = value
    return tags

def usertags(tags):
    return dict([(z,v) for z,v in tags.items() if
                    not (isinstance(z, (int, long)) or z.startswith('__'))])

def writeable(tags):
    return [z for z in tags if not z.starswith('___') or z.startswith('~')]

def isempty(value):
    if isinstance(value, (int, long)):
        return False
    if not value:
        return True

    try:
        return not [z for z in value if z or isinstance(z, (int, long))]
    except TypeError:
        return False

def getdeco(func):
    def f(self, key):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key])
        elif key in self.mapping:
            raise KeyError(key)
        return func(self, key)
    return f

def keys_deco(func):
    def f(self):
        if not self.revmapping:
            return func(self)
        else:
            mapping = self.mapping
            revmapping = self.revmapping
            return [mapping.get(k, k) for k in func(self)
                if not(k in revmapping and k not in mapping)]
    return f

def setdeco(func):
    def f(self, key, value):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key], value)
        elif key in self.mapping:
            return
        return func(self, key, value)
    return f

def del_deco(func):
    def f(self, key):
        mapping = self.revmapping
        if key in mapping:
            return func(self, mapping[key])
        return func(self, key)
    return f

def reversedict(d):
    return dict(((v,k) for k in d))

_sizes = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
def str_filesize(size):
    valid = [z for z in _sizes if size / (1024.0**z) > 1]
    val = max(valid)
    return '%.2f %s' % (size/(1024.0**val), _sizes[val])

def to_string(value, errors='strict'):
    if not value:
        return u''
    elif isinstance(value, str):
        return value.decode('utf8', errors)
    elif isinstance(value, unicode):
        return value
    elif isinstance(value, (int, long)):
        return unicode(value)
    else:
        return to_string(value[0])

def path_to_string(value):
    if not value:
        return ''
    elif isinstance(value, basestring):
        return encode_fn(value)
    else:
        return path_to_string(value[0])

def get_mime(data):
    mime = imghdr.what(None, data)
    if mime:
        return 'image/' + mime
    else:
        return u''

def get_total(tag):
    value = to_string(tag['track'])
    try:
        return value.split(u'/')[1].strip()
    except IndexError:
        raise KeyError('__total')

def set_total(tag, value):
    track = to_string(tag['track']).split(u'/', 1)
    value = to_string(value)
    if not (value and track) or len(track) == 1:
        return False
    tag['track'] = track[0] + u'/' + value
    return True

def cover_info(images, d=None):
    info = {}
    if not images:
        info[NUM_IMAGES] = u'0'
        info[IMAGE_MIMETYPE] = u''
    else:
        info[NUM_IMAGES] = unicode(len(images))
        image = images[0]
        if MIMETYPE in image:
            info[IMAGE_MIMETYPE] = image[MIMETYPE]
        else:
            info[IMAGE_MIMETYPE] = get_mime(image[DATA])

    if d:
        if not info[IMAGE_MIMETYPE]:
            del(info[IMAGE_MIMETYPE])
            try: del(d[IMAGE_MIMETYPE])
            except KeyError: pass
        d[NUM_IMAGES] = info[NUM_IMAGES]
    return info

class CaselessDict(dict):
    def __init__(self, other=None):
        self._keys = {}
        if other:
            # Doesn't do keyword args
            if isinstance(other, dict):
                for k,v in other.items():
                    self[k] = v
            else:
                for k,v in other:
                    self[k] = v

    def __getitem__(self, key):
        return dict.__getitem__(self, self._keys[key.lower()])

    def __setitem__(self, key, value):
        low = key.lower()
        dict.__setitem__(self, key, value)
        if self._keys.get(low, key) != key:
            dict.__delitem__(self, self._keys[low])
        self._keys[low] = key

    def __contains__(self, key):
        return key.lower() in self._keys

    def has_key(self, key):
        return key.lower() in self._keys

    def get(self, key, def_val=None):
        if key in self:
            return self[key]
        else:
            return def_val

    def update(self, other):
        for k,v in other.items():
            self[k] = v

    def fromkeys(self, iterable, value=None):
        d = CaselessDict()
        for k in iterable:
            d[k] = value
        return d
    
    def __delitem__(self, key):
        dict.__delitem__(self, self._keys[key.lower()])
        del(self._keys[key.lower()])

class MockTag(object):
    """Use as base for all tag classes."""

    def __init__(self, filename = None):
        object.__init__(self)
        self._info = {}
        self._filepath = ''
        if filename:
            self.link(filename)

    def get_filepath(self):
        return self.__filepath

    def set_filepath(self,  val):
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

    def _set_ext(self,  val):
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

    def set_attrs(self, attrs, tags=None):
        if tags is None:
            tags = self
        [setattr(self, z, tags['__%s' % z]) for z in attrs if
            '__%s' % z in tags]

    def load(self, filename, filetype=None):
        filename = getfilename(filename)
        self.filepath = filename
        if filetype is not None:
            audio = filetype(filename)
        else:
            audio = None
        tags = getinfo(filename)
        return tags, audio

    def update(self, dictionary=None, **kwargs):
        if dictionary is None:
            return
        if hasattr(dictionary, 'items'):
            for key, value in dictionary.items():
                self[key] = value
        else:
            for key, value in dictionary:
                self[key] = value

    def clear(self):
        keys = self._tags.keys()
        for z in keys:
            if not z.startswith('__'):
                del(self._tags[z])

    def keys(self):
        if not self.mapping:
            return self._tags.keys()
        else:
            mapping = self.mapping
            revmapping = self.revmapping
            return [mapping.get(k, k) for k in self._tags
                if not(k in revmapping and k not in mapping)]

    def values(self):
        return [self[key] for key in self]

    def items(self):
        return [(key, self[key]) for key in self]

    tags = property(lambda self: dict(self.items()))

    def __iter__(self):
        return self.keys().__iter__()

    def __len__(self):
        try:
            return self._tags.__len__()
        except AttributeError:
            return 0 #This means that that bool(self) = False

    def stringtags(self):
        return stringtags(self)

    def save(self):
        if not path.exists(self.filepath):
            raise IOError(ENOENT, os.strerror(ENOENT), self.filepath)

    def _usertags(self):
        return usertags(self)

    usertags = property(_usertags)

    def get(self, key, default=None):
        return self[key] if key in self else default

    def real(self, key):
        if key in self.revmapping:
            return self.revmapping[key]
        return key

    def sget(self, key):
        if key in self:
            return to_string(self[key])
        return ''