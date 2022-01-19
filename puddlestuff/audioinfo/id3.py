from collections import defaultdict
from copy import deepcopy
from functools import partial

import mutagen.id3 as id3
import mutagen.mp3

try:
    from mutagen.aiff import AIFF, _IFFID3
except ImportError:
    AIFF = None

try:
    from mutagen.dsf import DSF, _DSFID3
except ImportError:
    DSF = None

from mutagen.id3 import (APIC, PairedTextFrame, TextFrame, TimeStampTextFrame,
                         UrlFrame)

from . import util
from ._compatid3 import CompatID3

from .constants import MODES
from .util import (CaselessDict, FILENAME, MockTag, PATH,
                   cover_info, del_deco, fn_hash, get_mime, get_total,
                   getdeco, info_to_dict, isempty, keys_deco, parse_image, set_total,
                   setdeco, str_filesize, unicode_list, usertags)

TagBase = MockTag


# Placed here to prohibit the circular import from tag_versions.
def handle(audio):
    """Converts mutagen.id3.ID3 object to format puddletag understands.

    Returns a dictionary with the following a puddletag fields
    as keys eg. 'title'. Values associated with each field contain
    the mutagen.id3.Frame associated with that field.

    Each Frame object is modified to have get_value and set_value
    methods. Some frames will also have a 'frames' attributes.
    """

    # See the comment in for 'Tag.__tags' in 'Tag.__init__' for more info.
    handlers = defaultdict(lambda: [])

    for frame in audio.values():
        if frame.__class__ in frames:
            handlers[frames[frame.__class__]].append(frame)

    keys = {}
    ret = {}

    # Handler returns a dictionary with fields as used in puddletag
    # eg 'title' and text, a frame, or a list of frames as its
    # associated value.
    for handler, frame in handlers.items():
        for k, v in handler(frame).items():
            lower = k.lower()
            if lower in keys:
                ret[keys[lower]].append(v) if isinstance(v, str) \
                    else ret[keys[lower]].extend(v)
            else:
                keys[lower] = k
                ret[k] = v
    return ret


from . import tag_versions

ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
              'modified', 'filetype')

WRITE_V1 = 1
WRITE_V2 = 2
WRITE_BOTH = 3

v1_option = 2
v2_option = 4
apev2_option = False

ISO8859 = 0
UTF16 = 1
UTF16BE = 2
UTF8 = 3

encoding = UTF8


def get_factory(func, frame):
    return lambda: func(frame)


def set_factory(func, frame):
    return lambda value: func(frame, value)


def create_text(title, value):
    frame = revtext_frames[title](encoding, value)
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_text, frame)
    return {title: frame}


def get_text(textframe):
    return [str(z) for z in textframe.text]


def set_text(frame, value):
    frame.text = TextFrame(encoding, value).text
    frame.encoding = encoding
    return True


def text_handler(title):
    def func(frames):
        frame = frames[0]
        frame.get_value = lambda: get_text(frame)
        frame.set_value = partial(set_text, frame)
        return {title: frame}

    return func


def create_genre(value):
    frame = id3.TCON(encoding, value)
    frame.get_value = lambda: get_genre(frame)
    frame.set_value = lambda value: set_genre(frame, value)
    return {'genre': frame}


def get_genre(frame):
    return frame.genres


def set_genre(frame, value):
    frame.genres = value
    frame.encoding = encoding
    return True


def genre_handler(frames):
    frame = frames[0]
    frame.get_value = lambda: get_genre(frame)
    frame.set_value = lambda value: set_genre(frame, value)
    return {'genre': frame}


text_frames = {
    id3.TALB: 'album',
    id3.TBPM: 'bpm',
    id3.TCOM: 'composer',
    id3.TCOP: "copyright",
    id3.TDAT: "date",
    id3.TDLY: "audiodelay",
    id3.TENC: "encodedby",
    id3.TEXT: "lyricist",
    id3.TFLT: "filetype",
    id3.TIME: "time",
    id3.TIT1: "grouping",
    id3.TIT2: "title",
    id3.TIT3: "version",
    id3.TKEY: "initialkey",
    id3.TLAN: "language",
    id3.TLEN: "audiolength",
    id3.TMED: "mediatype",
    id3.TMOO: "mood",
    id3.TOAL: "originalalbum",
    id3.TOFN: "filename",
    id3.TOLY: "author",
    id3.TOPE: "originalartist",
    id3.TORY: "originalyear",
    id3.TOWN: "fileowner",
    id3.TPE1: "artist",
    id3.TPE2: "albumartist",
    id3.TPE3: "conductor",
    id3.TPE4: "arranger",
    id3.TPOS: "discnumber",
    id3.TPRO: "producednotice",
    id3.TPUB: "organization",
    id3.TRCK: "track",
    id3.TRDA: "recordingdates",
    id3.TRSN: "radiostationname",
    id3.TRSO: "radioowner",
    id3.TSIZ: "audiosize",
    id3.TSOA: "albumsortorder",
    id3.TSOP: "performersortorder",
    id3.TSOT: "titlesortorder",
    id3.TSRC: "isrc",
    id3.TSSE: "encodingsettings",
    id3.TSST: "setsubtitle",
    id3.TYER: 'year'}

try:
    text_frames.update({
        id3.TCMP: "itunescompilationflag",
        id3.TSO2: "itunesalbumsortorder",
        id3.TSOC: "itunescomposersortorder"})
except AttributeError:
    pass

revtext_frames = dict((key, frame) for frame, key in text_frames.items())
write_frames = dict((key, partial(create_text, key)) for
                    key in text_frames.values())
write_frames['genre'] = create_genre


def create_time(title, value):
    frame = revtime_frames[title](encoding)
    if not set_time(frame, value):
        return {}
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_time, frame)
    return {title: frame}


def set_time(frame, value):
    text = TimeStampTextFrame(encoding, value).text
    if not [_f for _f in text if _f]:
        return
    frame.text = text
    frame.encoding = encoding
    return True


def time_handler(title):
    def func(frames):
        frame = frames[0]
        frame.get_value = lambda: get_text(frame)
        frame.set_value = partial(set_time, frame)
        return {title: frame}

    return func


time_frames = {
    id3.TDEN: "encodingtime",
    id3.TDOR: "originalreleasetime",
    id3.TDRC: "year",
    id3.TDRL: "releasetime",
    id3.TDTG: "taggingtime"}

revtime_frames = dict([(key, frame) for frame, key in time_frames.items()])
write_frames.update([(key, partial(create_time, key)) for
                     key in revtime_frames])


def create_usertext(title, value):
    frame = id3.TXXX(encoding, title, value)
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_text, frame)
    return {title: frame}


def usertext_handler(frames):
    d = {}
    for frame in frames:
        frame.get_value = get_factory(get_text, frame)
        frame.set_value = set_factory(set_text, frame)
        d[frame.desc] = frame
    return d


url_frames = {
    id3.WCOP: "wwwcopyright",
    id3.WOAF: "wwwfileinfo",
    id3.WOAS: "wwwsource",
    id3.WORS: "wwwradio",
    id3.WPAY: "wwwpayment",
    id3.WPUB: "wwwpublisher"}


def create_url(title, value):
    frame = revurl_frames[title]()
    frame.get_value = lambda: get_url(frame)
    frame.set_value = partial(set_url, frame)
    frame.set_value(value)
    return {title: frame}


def get_url(frame):
    return [frame.url]


def set_url(frame, value):
    if not isinstance(value, str):
        value = value[0]
    frame.url = UrlFrame(value).url
    return True


def url_handler(title):
    def func(frames):
        frame = frames[0]
        frame.get_value = lambda: get_url(frame)
        frame.set_value = partial(set_url, frame)
        return {title: frame}

    return func


revurl_frames = dict([(key, frame) for frame, key in url_frames.items()])
write_frames.update([(key, partial(create_url, key)) for key in revurl_frames])

uurl_frames = {
    id3.WCOM: "wwwcommercialinfo",
    id3.WOAR: "wwwartist"}


def create_uurl(title, value):
    frame = revuurl_frames[title]()
    d = uurl_handler(title)([frame])
    d[title].set_value(value)
    return d


def uurl_handler(title):
    def set_uurl(frames, value):
        if isinstance(value, str):
            value = [value]
        while frames:
            frames.pop()
        cls = revuurl_frames[title]
        frames.extend([cls(v) for v in value])

    def func(frames):
        frame = frames[0]
        frame.get_value = lambda: [f.url for f in frames]
        frame.set_value = partial(set_uurl, frames)
        frame.frames = frames
        return {title: frame}

    return func


revuurl_frames = dict([(key, frame) for frame, key in uurl_frames.items()])
write_frames.update([(key, partial(create_uurl, key)) for
                     key in revuurl_frames])


def create_userurl(title, value):
    value = to_string(value)
    desc = title[len('www:'):]
    frame = id3.WXXX(encoding, desc, value)
    frame.get_value = lambda: get_url(frame)
    frame.set_value = partial(set_url, frame)
    return {title: frame}


def userurl_handler(frames):
    d = {}
    for frame in frames:
        frame.get_value = get_factory(get_url, frame)
        frame.set_value = set_factory(set_url, frame)
        d['www:' + frame.desc] = frame
    return d


paired_textframes = {
    id3.TIPL: "involvedpeople",
    id3.TMCL: "musiciancredits",
    id3.IPLS: "involvedpeople"}


def create_paired(key, value):
    frame = revpaired_frames[key](encoding)
    if set_paired(frame, value):
        frame.get_value = get_factory(get_paired, frame)
        frame.set_value = set_factory(set_paired, frame)
        return {key: frame}
    return {}


def get_paired(frame):
    return [';'.join([':'.join(z) for z in frame.people])]


def set_paired(frame, text):
    if not isinstance(text, str):
        text = text[0]
    value = [people.split(':') for people in text.split(';')]
    temp = []
    for pair in value:
        if len(pair) == 1:
            temp.append([pair[0], ''])
        else:
            temp.append(pair)
    value = temp
    frame.people = PairedTextFrame(encoding, value).people
    return True


def paired_handler(title):
    def func(frame):
        frame = frame[0]
        frame.get_value = lambda: get_paired(frame)
        frame.set_value = partial(set_paired, frame)
        return {title: frame}

    return func


revpaired_frames = dict([(key, frame) for frame,
                                          key in paired_textframes.items()])
write_frames.update([(key, partial(create_paired, key)) for
                     key in revpaired_frames])


def create_comment(desc, value):
    frame = id3.COMM(encoding, 'XXX', desc, value)
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_text, frame)
    return {'comment:' + frame.desc: frame}


def set_commentattrs(frame):
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_text, frame)


def comment_handler(frames):
    d = {}
    for frame in frames:
        set_commentattrs(frame)
        if not frame.desc and 'comment' not in d:
            d['comment'] = frame
        else:
            d['comment:' + frame.desc] = frame
    return d


def create_playcount(value):
    frame = id3.PCNT()
    if set_playcount(frame, value):
        frame.get_value = lambda: get_playcount(frame)
        frame.set_value = partial(set_playcount, frame)
        return {'playcount': frame}
    return {}


def get_playcount(frame):
    return [str(frame.count)]


def set_playcount(frame, value):
    if not isinstance(value, str):
        value = value[0]
    try:
        frame.count = int(value)
    except ValueError:
        return
    return True


def playcount_handler(frame):
    frame = frame[0]
    frame.get_value = lambda: get_playcount(frame)
    frame.set_value = partial(set_playcount, frame)
    return {'playcount': frame}


def create_popm(values):
    if isinstance(values, str):
        values = [values]
    frames = [_f for _f in [set_popm(id3.POPM(), v) for v in values] if _f]
    if frames:
        return popm_handler(frames)
    return {}


def get_popm(frame):
    if not hasattr(frame, 'count'):
        frame.count = 0
    return ':'.join([frame.email, str(frame.rating),
                     str(frame.count)])


def to_string(value):
    if isinstance(value, str):
        return value
    else:
        return to_string(value[0])


def set_popm(frame, value):
    value = to_string(value)
    try:
        email, rating, count = value.split(':', encoding)
        rating = int(rating)
        count = int(count)
    except ValueError:
        return
    frame.email = email
    frame.rating = rating
    frame.count = count
    return frame


def popm_handler(frames):
    def set_values(frames, values):
        if isinstance(values, str):
            values = [values]
        temp = [_f for _f in [set_popm(id3.POPM(), v) for v in values] if _f]
        if not temp:
            return
        while frames:
            frames.pop()
        [frames.append(v) for v in temp]

    get_value = lambda: [get_popm(f) for f in frames]
    set_value = partial(set_values, frames)

    for frame in frames:
        frame.get_value = get_value
        frame.set_value = set_value
        frame.frames = frames
    return {'popularimeter': frame}


def create_ufid(key, value):
    if not isinstance(value, str):
        try:
            value = value[0]
        except IndexError:
            return {}
    owner = key[len('ufid:'):]
    frame = id3.UFID(owner, value)
    frame.get_value = partial(get_ufid, frame)
    frame.set_value = partial(set_ufid, frame)
    return {'ufid:' + frame.owner: frame}


def set_ufid(frame, value):
    if not isinstance(value, str):
        try:
            value = value[0]
        except IndexError:
            return {}
    frame.data = value


def get_ufid(frame):
    return [frame.data]


def ufid_handler(frames):
    d = {}
    for frame in frames:
        frame.get_value = get_factory(get_ufid, frame)
        frame.set_value = set_factory(set_ufid, frame)
        d['ufid:' + frame.owner] = frame
    return d


def _parse_rgain(value):
    if not isinstance(value, str):
        try:
            value = value[0]
        except IndexError:
            return

    values = [z.strip() for z in value.split(':')]
    channel, gain, peak = values
    channel = int(channel)
    gain = float(gain)
    peak = float(peak)
    return channel, gain, peak


def create_rgain(key, value):
    desc = key[len('rgain:'):]
    try:
        channel, gain, peak = _parse_rgain(value)
    except (TypeError, ValueError):
        return {}

    frame = id3.RVA2(desc, channel, gain, peak)
    frame.get_value = get_factory(get_rgain, frame)
    frame.set_value = set_factory(set_rgain, frame)

    return {'rgain:' + desc: frame}


def set_rgain(frame, value):
    try:
        channel, gain, peak = _parse_rgain(value)
    except (TypeError, ValueError):
        return {}
    frame.channel = channel
    frame.gain = gain
    frame.peak = peak


def get_rgain(frame):
    return ':'.join(map(str, [frame.channel, frame.gain, frame.peak]))


def rgain_handler(frames):
    d = {}
    for f in frames:
        f.get_value = get_factory(get_rgain, f)
        f.set_value = set_factory(set_rgain, f)
        d['rgain:' + f.desc] = f
    return d


def create_uslt(value):
    f = id3.USLT()
    set_uslt(f, value)
    f.set_value = set_factory(set_uslt, f)
    if f.frames:
        return {'unsyncedlyrics': f}
    return {}


def set_uslt(f, value):
    if isinstance(value, str):
        value = [value]

    frames = []

    for lyrics in value:
        try:
            lyrics = [z for z in lyrics.split('|', 3)]
        except (TypeError, ValueError):
            continue
        len_l = len(lyrics)
        if len_l == 1:
            lang = 'XXX'
            desc = ''
            text = lyrics[0]
        elif len_l == 2:
            lang = lyrics[0].strip()
            desc = ''
            text = lyrics[1]
        elif len_l == 3:
            lang, desc, text = lyrics
            lang = lang.strip()
        elif len_l > 3:
            text = ''.join(lyrics[2:])
            lang = lyrics[0].strip()
            desc = lyrics[1]
        else:
            continue

        if not lang:
            lang = 'XXX'
        frames.append(id3.USLT(encoding, lang, desc, text))

    if not frames:
        f.frames = []
        f.get_value
        return {}

    f.frames = frames
    f.get_value = get_uslt(frames)


def get_uslt(frames):
    def text(f, attr):
        ret = getattr(f, attr, '')
        return ret if isinstance(ret, str) else \
            str(ret, 'utf8', 'replace')

    ret = ['%s|%s|%s' % (text(frame, 'lang'), text(frame, 'desc'),
                          text(frame, 'text')) for frame in frames]
    return lambda: ret


def uslt_handler(frames):
    d = {}
    f = frames[0]
    f.get_value = get_uslt(frames)
    f.set_value = set_factory(set_uslt, f)
    f.frames = frames
    d['unsyncedlyrics'] = f
    return d


write_frames.update({
    'playcount': create_playcount,
    'popularimeter': create_popm,
    'genre': create_genre,
    'unsyncedlyrics': create_uslt})

# Dictionary contaning classes from mutagen.id3 and it's associated
# handler.
frames = dict([(key, text_handler(title)) for key,
                                              title in text_frames.items()])

frames.update([(key, time_handler(title)) for key, title in
               time_frames.items()])

frames.update([(key, url_handler(title)) for key, title in
               url_frames.items()])

frames.update([(key, uurl_handler(title)) for key, title in
               uurl_frames.items()])

frames.update([(key, paired_handler(title)) for key, title in
               paired_textframes.items()])

frames.update({
    id3.TCON: genre_handler,
    id3.WXXX: userurl_handler,
    id3.TXXX: usertext_handler,
    id3.COMM: comment_handler,
    id3.PCNT: playcount_handler,
    id3.POPM: popm_handler,
    id3.UFID: ufid_handler,
    id3.RVA2: rgain_handler,
    id3.USLT: uslt_handler, })

revframes = dict((v, k) for k, v in frames.items())


def bin_to_pic(image):
    return {'data': image.data, 'description': image.desc,
            'mime': image.mime, 'imagetype': image.type}


def pic_to_bin(image):
    data = image[util.DATA]
    description = image.get(util.DESCRIPTION)
    if not description:
        description = ''
    imagetype = image.get(util.IMAGETYPE, encoding)
    mime = image.get(util.MIMETYPE)
    if not mime:
        mime = get_mime(data)
    return APIC(encoding, mime, imagetype, description, data)


class ID3(CompatID3):
    """ID3 reader to replace mutagen's just to allow the reading of APIC
    tags with the same description, ala Mp3tag."""
    PEDANTIC = True

    def loaded_frame(self, tag):
        if len(type(tag).__name__) == encoding:
            tag = type(tag).__base__(tag)
        i = 0
        try:
            desc = tag.desc
            while tag.HashKey in self:
                tag.desc = desc + str(i)
                i += 1
        except AttributeError:
            "Nothing to do"
        self[tag.HashKey] = tag


class ID3FileType(mutagen.mp3.MP3):
    """See ID3 class."""

    def add_tags(self, ID3=ID3):
        return super(ID3FileType, self).add_tags(ID3)

    def load(self, filename, ID3=ID3, **kwargs):
        return super(ID3FileType, self).load(filename, ID3, **kwargs)


if AIFF is not None:
    class AIFFFileType(AIFF):
        """See ID3 class."""

        def add_tags(self, ID3=_IFFID3):
            AIFF.add_tags(self)

        def load(self, filename, **kwargs):
            return AIFF.load(self, filename, **kwargs)

if DSF is not None:
    class DSFFileType(DSF):
        """See ID3 class."""

        def add_tags(self, ID3=_IFFID3):
            DSF.add_tags(self)

        def load(self, filename, **kwargs):
            return DSF.load(self, filename, **kwargs)


def tag_factory(id3_filetype):
    class Tag(TagBase):
        IMAGETAGS = (util.MIMETYPE, util.DESCRIPTION, util.DATA,
                     util.IMAGETYPE)
        mapping = {}
        revmapping = {}

        def __init__(self, filename=None):
            self.__images = []

            self.__tags = CaselessDict()  # Used as storage.
            # Each key as the is the field as used by puddletag, eg. 'artist'
            # Each value contains an mutagen.id3.Frame object
            # that have two methods, get_value and set_value.
            # get_value returns the value stored by the frame as
            # text/unicode list.
            # set_value should take text/unicode list in parse it into
            # it understands.

            # When saving the frame stored will be used. If it has a 'frames'
            # attributes, those frames will be used instead.

            util.MockTag.__init__(self, filename)

        def get_filepath(self):
            return util.MockTag.get_filepath(self)

        def set_filepath(self, val):
            self.__tags.update(util.MockTag.set_filepath(self, val))

        filepath = property(get_filepath, set_filepath)

        def _get_images(self):
            return self.__images

        def _set_images(self, images):
            if images:
                self.__images = [parse_image(i, self.IMAGETAGS) for i in images]
            else:
                self.__images = []
            cover_info(images, self.__tags)

        images = property(_get_images, _set_images)

        def _info(self):
            info = self.mut_obj.info
            fileinfo = [('Path', self[PATH]),
                        ('Size', str_filesize(int(self.size))),
                        ('Filename', self[FILENAME]),
                        ('Modified', self.modified)]
            try:
                version = self.mut_obj.tags.version
                version = ('ID3 Version', self.filetype)
            except AttributeError:
                version = ('ID3 Version', 'No tags in file.')
            fileinfo.append(version)

            if isinstance(self.mut_obj, DSFFileType):
                mpginfo = [('Type', 'DSF')]
            elif isinstance(self.mut_obj, AIFFFileType):
                mpginfo = [('Type', 'AIFF')]
            elif (self.mut_obj, ID3FileType):
                mpginfo = [('Version', 'MPEG %i Layer %i' % (info.version, info.layer))]
            else:
                mpginfo = []

            try:
                mpginfo.append(('Bitrate', self.bitrate))
            except AttributeError:
                pass

            try:
                mpginfo.append(('Frequency', self.frequency))
            except AttributeError:
                pass

            try:
                mpginfo.append(('Mode', MODES[info.mode]))
            except AttributeError:
                pass

            try:
                mpginfo.append(('Length', self.length))
            except Att:
                pass

            return [('File', fileinfo), (mpginfo[0][0], mpginfo)]

        info = property(_info)

        def __contains__(self, key):
            if key == '__image':
                return bool(self.images)

            elif key == '__total':
                try:
                    return bool(get_total(self))
                except (KeyError, ValueError):
                    return False

            if self.revmapping:
                key = self.revmapping.get(key, key)

            return key in self.__tags

        def __deepcopy__(self, memo=None):
            cls = Tag()
            tags = CaselessDict()
            frames = []
            [frames.append(frame) if not hasattr(frame, 'frames') else
             frames.extend(frame.frames) for key, frame in self.__tags.items()
             if not key.startswith('__')]
            funcs = []
            frames_copy = []
            for frame in frames:
                funcs.append((getattr(frame, 'get_value', None),
                              getattr(frame, 'set_value', None)))
                if hasattr(frame, 'get_value'):
                    delattr(frame, 'get_value')
                if hasattr(frame, 'set_value'):
                    delattr(frame, 'set_value')
                frames_copy.append(deepcopy(frame))
            tags = handle(dict([(frame.HashKey, frame) for frame in frames_copy]))
            for frame, (get_value, set_value) in zip(frames, funcs):
                if get_value is not None:
                    frame.get_value = get_value
                if set_value is not None:
                    frame.set_value = set_value
            for key, value in self.__tags.items():
                if key not in tags:
                    tags[key] = deepcopy(value)
            cls.set_fundamentals(tags,
                                 self.mut_obj, deepcopy(self.images))
            cls.filepath = self.filepath
            return cls

        @del_deco
        def __delitem__(self, key):
            if key == '__image':
                self.images = []
            elif key.startswith('__'):
                return
            else:
                del (self.__tags[key])

        @getdeco
        def __getitem__(self, key):
            if key.startswith('__'):
                if key == '__image':
                    return self.images
                elif key == '__filetype':
                    return self.filetype
                elif key == '__total':
                    return get_total(self)
                else:
                    return self.__tags[key]
            elif not isinstance(key, str):
                return self.__tags[key]
            else:
                return self.__tags[key].get_value()

        @setdeco
        def __setitem__(self, key, value):
            if not isinstance(key, str):
                self.__tags[key] = value
                return
            if key.startswith('__'):
                if key == '__image':
                    self.images = value
                elif key in fn_hash:
                    setattr(self, fn_hash[key], value)
                elif key == '__total':
                    set_total(self, value)
                return

            value = unicode_list(value)

            if isempty(value):
                if key in self:
                    del (self[key])
                return

            if key in self.__tags:
                self.__tags[key].set_value(value)
            else:
                if key in write_frames:
                    self.__tags.update(write_frames[key](value))
                elif key == 'comment':
                    frame = {'comment': create_comment('', value)['comment:']}
                    self.__tags.update(frame)
                elif key.startswith('comment:'):
                    self.__tags.update(create_comment(key[len('comment:'):], value))
                elif key.startswith('www:'):
                    self.__tags.update(create_userurl(key, value))
                elif key.startswith('ufid:'):
                    self.__tags.update(create_ufid(key, value))
                elif key.startswith('rgain:'):
                    self.__tags.update(create_rgain(key, value))
                elif key.startswith('unsyncedlyrics:'):
                    self.__tags.update(create_uslt(key, value))
                else:
                    self.__tags.update(create_usertext(key, value))

        def delete(self):
            self.mut_obj.delete()
            for key in self.usertags:
                del (self.__tags[self.revmapping.get(key, key)])
            self.images = []

        @keys_deco
        def keys(self):
            return list(self.__tags.keys())

        def link(self, filename):
            """Links the audio, filename
            returns self if successful, None otherwise."""
            self.__images = []
            tags, audio = self.load(filename, id3_filetype)
            if audio is None:
                return

            if audio.tags:  # Not empty
                audio.tags.update_to_v24()
                self.__tags.update(handle(audio))

                # Get the image data.
                apics = audio.tags.getall("APIC")
                if apics:
                    self.images = list(map(bin_to_pic, apics))
                else:
                    self.images = [];

            self.__tags.update(tags)
            self.__tags.update(info_to_dict(audio.info))

            if self.ext.lower() == 'mp3':
                self.__tags['__filetype'] = 'MP3'
            else:
                self.__tags['__filetype'] = 'ID3'

            self.set_attrs(ATTRIBUTES, self.__tags)

            try:
                self.__tags['__tag_read'] = 'ID3v%s.%s' % audio.tags.version[:2]
            except AttributeError:
                self.__tags['__tag_read'] = ''
            self.mut_obj = audio
            self._originaltags = list(audio.keys())
            self.update_tag_list()
            return self

        def save(self, v1=None, v2=None):
            if v1 is None:
                v1 = v1_option
            """Writes the tags to file."""
            filename = self.filepath
            if self.mut_obj.tags is None:
                self.mut_obj.add_tags()
            if filename != self.mut_obj.filename:
                self.mut_obj.tags.filename = filename
                self.mut_obj.filename = filename
            audio = self.mut_obj
            util.MockTag.save(self)

            userkeys = list(usertags(self.__tags).keys())
            frames = []
            [frames.append(frame) if not hasattr(frame, 'frames') else
             frames.extend(frame.frames) for key, frame in self.__tags.items()
             if key in userkeys]
            hashes = dict([(frame.HashKey, frame) for frame in frames])
            toremove = [z for z in self._originaltags if z in audio
                        and not (z in hashes or z.startswith('APIC'))]
            audio.update(hashes)

            old_apics = [z for z in audio if z.startswith('APIC')]
            if self.__images:
                newimages = []
                for image in [_f for _f in map(pic_to_bin, self.__images) if _f]:
                    i = 0
                    while image.HashKey in newimages:
                        i += 1
                        # Pad with spaces so that each key is unique.
                        image.desc += ' ' * i
                    audio[image.HashKey] = image
                    newimages.append(image.HashKey)
                [toremove.append(z) for z in old_apics if z not in newimages]
            else:
                toremove.extend(old_apics)

            for z in set(toremove):
                try:
                    del (audio[z])
                except KeyError:
                    continue

            audio.tags.filename = self.filepath
            v1 = v1_option if v1 is None else v1
            v2 = v2_option if v2 is None else v2

            if AIFF is not None and id3_filetype is AIFFFileType:
                if v2 == 3:
                    audio.tags.save(v2_version=3)  # AIFF doesn't support id3v1
                else:
                    audio.tags.save()  # AIFF doesn't support id3v1

            elif DSF is not None and id3_filetype is DSFFileType:
                if v2 == 3:
                    audio.tags.save(v2_version=3)  # DSF doesn't support id3v1
                else:
                    audio.tags.save()  # DSF doesn't support id3v1
            else:
                if v2 == 4:
                    audio.tags.update_to_v24()
                    audio.tags.save(v1=v1, v2_version=4)
                else:
                    c = ID3()
                    c.filename = self.filepath
                    c.update(audio)
                    c.update_to_v23()
                    c.save(v1=v1, v2_version=3)

            self.__tags['__tag_read'] = 'ID3v2.4' if v2 == 4 else 'ID3v2.3'
            self.update_tag_list()
            self._originaltags = list(audio.keys())

        def set_fundamentals(self, tags, mut_obj, images=None):
            self.__tags = tags
            self.mut_obj = mut_obj
            if images:
                self.images = images
            self._originaltags = list(tags.keys())
            self.set_attrs(ATTRIBUTES, tags)

        def to_encoding(self, encoding=UTF8):
            frames = []
            saved = []
            for frame in self.__tags.values():
                if hasattr(frame, 'encoding'):
                    frames.append((frame, frame.encoding))
                    frame.encoding = encoding
            try:
                self.save(v2=4)
            except:
                for frame, enc in frames:
                    frame.encoding = enc
                raise

        def update_tag_list(self):
            tag = self.__tags['__tag_read']
            l = tag_versions.tags_in_file(self.filepath)
            if l:
                if tag and tag in l:
                    l.remove(tag)
                    l.insert(0, tag)
                self.__tags['__tag'] = ', '.join(l)
            else:
                self.__tags['__tag'] = tag

    return Tag


Tag = tag_factory(ID3FileType)

filetypes = [
    (ID3FileType, tag_factory(ID3FileType), 'ID3', 'mp3'),
]

if AIFF is not None:
    filetypes.append((AIFFFileType, tag_factory(AIFFFileType), 'AIFF', 'aiff'))

if DSF is not None:
    filetypes.append((DSFFileType, tag_factory(DSFFileType), 'DSF', ['dsf', 'dff']))
