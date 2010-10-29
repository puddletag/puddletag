# -*- coding: utf-8 -*-
import sys
import mutagen.id3 as id3
import unittest, pdb
import mutagen
from functools import partial
from mutagen.id3 import TextFrame, TimeStampTextFrame, UrlFrame, UrlFrameU, PairedTextFrame
from collections import defaultdict
from util import *
TagBase = MockTag
import util

import mutagen, mutagen.id3, mutagen.mp3, pdb, util
from copy import copy, deepcopy
APIC = mutagen.id3.APIC
TimeStampTextFrame = mutagen.id3.TimeStampTextFrame
TextFrame = mutagen.id3.TextFrame
ID3  = mutagen.id3.ID3
from util import  (strlength, strbitrate, strfrequency, isempty, getdeco,
    setdeco, getfilename, getinfo, FILENAME, PATH, INFOTAGS,
    READONLY, EXTENSION, DIRPATH, FILETAGS, str_filesize, DIRNAME)
import imghdr

MODES = ['Stereo', 'Joint-Stereo', 'Dual-Channel', 'Mono']
ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
              'modified')

WRITE_V1 = 1
WRITE_V2 = 2
WRITE_BOTH = 3

v1_option = 2
apev2_option = False

class PuddleID3(ID3):
    """ID3 reader to replace mutagen's just to allow the reading of APIC
    tags with the same description, ala Mp3tag."""
    PEDANTIC = True
    def loaded_frame(self, tag):
        if len(type(tag).__name__) == 3:
            tag = type(tag).__base__(tag)
        i = 0
        while tag.HashKey in self:
            try:
                tag.desc = tag.desc + unicode(i)
            except AttributeError:
                break
            i += 1
        self[tag.HashKey] = tag

class PuddleID3FileType(mutagen.mp3.MP3):
    """See PuddleID3."""
    def add_tags(self, ID3=PuddleID3):
        mutagen.mp3.MP3.add_tags(self, ID3)

    def load(self, filename, ID3 = PuddleID3, **kwargs):
        mutagen.mp3.MP3.load(self, filename, ID3, **kwargs)

def get_factory(func, frame):
    return lambda: func(frame)

def set_factory(func, frame):
    return lambda value: func(frame, value)

def create_text(title, value):
    frame = revtext_frames[title](3, value)
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_text, frame)
    return {title: frame}

def get_text(textframe):
    return [unicode(z) for z in textframe.text]

def set_text(frame, value):
    frame.text = TextFrame(3, value).text
    frame.encoding = 3
    return True

def text_handler(title):
    def func(frames):
        frame = frames[0]
        frame.get_value = lambda: get_text(frame)
        frame.set_value = partial(set_text, frame)
        return {title: frame}
    return func

text_frames ={
    id3.TALB: 'album',
    id3.TBPM: 'bpm',
    id3.TCOM: 'composer',
    id3.TCON: 'genre',
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
    id3.TPE2: "performer",
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
    id3.TSOP: "peformersortorder",
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

revtext_frames = dict([(key, frame) for frame, key in text_frames.items()])
write_frames = dict([(key, partial(create_text, key)) for key in text_frames.values()])

def create_time(title, value):
    frame = revtime_frames[title](3)
    if not set_time(frame, value):
        return {}
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_time, frame)
    return {title: frame}

def set_time(frame, value):
    text = TimeStampTextFrame(3, value).text
    if not filter(None, text):
        return
    frame.text = text
    frame.encoding = 3
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
    frame = id3.TXXX(3, title, value)
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
    if not isinstance(value, basestring):
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
        if isinstance(value, basestring):
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
    frame = id3.WXXX(3, desc, value)
    frame.get_value = lambda: get_url(frame)
    frame.set_value = partial(set_url, frame)
    return {title: frame}

def userurl_handler(frames):
    d = {}
    for frame in frames:
        frame.get_value = get_factory(get_url, frame)
        frame.set_value = set_factory(set_url, frame)
        d[u'www:'+ frame.desc] = frame
    return d

paired_textframes = {
    id3.TIPL: "involvedpeople",
    id3.TMCL: "musiciancredits",
    id3.IPLS: "involvedpeople"}

def create_paired(key, value):
    frame = revpaired_frames[key](3)
    if set_paired(frame, value):
        frame.get_value = get_factory(get_paired, frame)
        frame.set_value = set_factory(set_paired, frame)
        return {key: frame}
    return {}

def get_paired(frame):
    return [u';'.join([u':'.join(z) for z in frame.people])]

def set_paired(frame, text):
    if not isinstance(text, basestring):
        text = text[0]
    value = [people.split(':') for people in text.split(';')]
    temp = []
    for pair in value:
        if len(pair) == 1:
            temp.append([pair[0], u''])
        else:
            temp.append(pair)
    value = temp
    frame.people = PairedTextFrame(3, value).people
    return True

def paired_handler(title):
    def func(frame):
        frame = frame[0]
        frame.get_value = lambda: get_paired(frame)
        frame.set_value = partial(set_paired, frame)
        return {title: frame}
    return func

revpaired_frames = dict([(key, frame) for frame, key in paired_textframes.items()])
write_frames.update([(key, partial(create_paired, key)) for
                        key in revpaired_frames])

def create_comment(desc, value):
    frame = id3.COMM(3, 'XXX', desc, value)
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_text, frame)
    return {u'comment:' + frame.desc: frame}

def set_commentattrs(frame):
    frame.get_value = lambda: get_text(frame)
    frame.set_value = partial(set_text, frame)

def comment_handler(frames):
    d = {}
    for frame in frames:
        set_commentattrs(frame)
        if not frame.desc and 'comment' not in d:
            d[u'comment'] = frame
        else:
            d[u'comment:' + frame.desc] = frame
    return d

def create_playcount(value):
    frame = id3.PCNT()
    if set_playcount(frame, value):
        frame.get_value = lambda: get_playcount(frame)
        frame.set_value = partial(set_playcount, frame)
        return {'playcount': frame}
    return {}

def get_playcount(frame):
    return [unicode(frame.count)]

def set_playcount(frame, value):
    if not isinstance(value, basestring):
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
    return {u'playcount': frame}

def create_popm(values):
    if isinstance(values, basestring):
        values = [values]
    frames = filter(None, map(lambda v: set_popm(id3.POPM(), v), values))
    if frames:
        return popm_handler(frames)
    return {}

def get_popm(frame):
    if not hasattr(frame, 'count'):
        frame.count = 0
    return u':'.join([frame.email, unicode(frame.rating),
        unicode(frame.count)])

def to_string(value):
    if isinstance(value, str):
        return value.decode('utf8')
    elif isinstance(value, unicode):
        return value
    else:
        return to_string(value[0])


def set_popm(frame, value):
    value = to_string(value)
    try:
        email, rating, count = value.split(':', 3)
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
        if isinstance(values, basestring):
            values = [values]
        temp = filter(None, [set_popm(id3.POPM(), v) for v in values])
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
    if not isinstance(value, basestring):
        try:
            value = value[0]
        except IndexError:
            return {}
    if isinstance(value, unicode):
        value = value.decode('utf8')
    owner = key[len('ufid:'):]
    frame = id3.UFID(owner, value)
    frame.get_value = partial(get_ufid, frame)
    frame.set_value = partial(set_ufid, frame)
    return {u'ufid:' + frame.owner: frame}

def set_ufid(frame, value):
    if not isinstance(value, basestring):
        try:
            value = value[0]
        except IndexError:
            return {}
    if isinstance(value, unicode):
        value = value.decode('utf8')
    frame.data = value

def get_ufid(frame):
    return [frame.data.encode('utf8')]

def ufid_handler(frames):
    d = {}
    for frame in frames:
        frame.get_value = get_factory(get_ufid, frame)
        frame.set_value = set_factory(set_ufid, frame)
        d['ufid:' + frame.owner] = frame
    return d

def _parse_rgain(value):
    if not isinstance(value, basestring):
        try:
            value = value[0]
        except IndexError:
            return

    if isinstance(value, unicode):
        value = value.decode('utf8')

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
    except TypeError, ValueError:
        return {}

    return {'rgain:' + desc: id3.RVA2(desc, channel, gain, peak)}

def set_rgain(frame, value):
    try:
        channel, gain, peak = _parse_rgain(value)
    except TypeError, ValueError:
        return {}
    frame.channel = channel
    frame.gain = gain
    frame.peak = peak

def get_rgain(frame):
    return u':'.join(map(unicode, [frame.channel, frame.gain, frame.peak]))

def rgain_handler(frames):
    d = {}
    for f in frames:
        f.get_value = get_factory(get_rgain, f)
        f.set_value = set_factory(set_rgain, f)
        d['rgain:' + f.desc] = f
    return d
    

write_frames.update({'playcount': create_playcount,
                     'popularimeter': create_popm})

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

frames.update({id3.WXXX: userurl_handler,
               id3.TXXX: usertext_handler,
               id3.COMM: comment_handler,
               id3.PCNT: playcount_handler,
               id3.POPM: popm_handler,
               id3.UFID: ufid_handler,
               id3.RVA2: rgain_handler,})

revframes = dict([(val, key) for key, val in frames.items()])

def handle(f):
    d = defaultdict(lambda: [])
    for val in f.values():
        c = val.__class__
        if c in frames:
            d[frames[c]].append(val)
    ret = {}
    for func, val in d.items():
        ret.update(func(val))
    return ret

class Tag(TagBase):
    IMAGETAGS = (util.MIMETYPE, util.DESCRIPTION, util.DATA,
        util.IMAGETYPE)
    mapping = {}
    revmapping = {}

    @getdeco
    def __getitem__(self,key):
        """Get the tag value. There is a slight
        caveat in that this method will never return a KeyError exception.
        Rather it'll return ''."""
        if key == '__image':
            return self.images

        elif key in INFOTAGS or isinstance(key, (int,long)):
            return self._tags[key]
        else:
            return self._tags[key].get_value()

    def delete(self):
        self._mutfile.delete()
        for z in self.usertags:
            del(self._tags[z])
        self.images = []

    def _picture(self, image):
        data = image[util.DATA]
        description = image.get(util.DESCRIPTION)
        if not description:
            description = u''
        mime = image.get(util.MIMETYPE)
        imagetype = image.get(util.IMAGETYPE, 3)
        if not mime:
            t = imghdr.what(None, data)
            if t:
                mime = u'image/' + t
        return APIC(3, mime, imagetype, description, data)

    def _getImages(self):
        if self._images:
            return [{'data': image.data, 'description': image.desc,
                    'mime': image.mime, 'imagetype': image.type}
                        for image in self._images]
        return []

    def _setImages(self, images):
        if images:
            self._images = map(self._picture, images)
        else:
            self._images = []

    images = property(_getImages, _setImages)

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""
        self._images = []
        tags, audio = self._init_info(filename, PuddleID3FileType)
        if audio is None:
            return

        if audio.tags: #Not empty
            audio.tags.update_to_v24()
            self._tags.update(handle(audio))

            #Get the image data.
            x = audio.tags.getall("APIC")
            if x:
                self._images = x

        info = audio.info
        self._tags.update({u"__frequency": strfrequency(info.sample_rate),
                      u"__length": strlength(info.length),
                      u"__bitrate": strbitrate(info.bitrate)})
        self._tags.update(tags)
        try:
            version = audio.tags.version
            self.filetype = u'ID3v%s.%s' % audio.tags.version[:2]
        except AttributeError:
            self.filetype = u'ID3'
        self._tags['__filetype'] = self.filetype

        self._set_attrs(ATTRIBUTES)
        self._mutfile = audio
        self._originaltags = audio.keys()
        return self

    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]
        try:
            version = self._mutfile.tags.version
            version = ('ID3 Version', self.filetype)
        except AttributeError:
            version = ('ID3 Version', 'No tags in file.')
        fileinfo.append(version)

        mpginfo = [('Version', u'MPEG %i Layer %i' % (info.version, info.layer)),
                   ('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Mode', MODES[info.mode]),
                   ('Length', self.length)]

        return [('File', fileinfo), (mpginfo[0][0], mpginfo)]


    info = property(_info)

    def save(self):
        """Writes the tags to file."""
        filename = self.filepath
        if self._mutfile.tags is None:
            self._mutfile.add_tags()
        if filename != self._mutfile.filename:
            self._mutfile.tags.filename = filename
            self._mutfile.filename = filename
        audio = self._mutfile
        util.MockTag.save(self)

        #pdb.set_trace()
        userkeys = [self.revmapping.get(key, key) for key in self.usertags.keys()]
        frames = []
        [frames.append(frame) if not hasattr(frame, 'frames') else
            frames.extend(frame.frames) for key, frame in self._tags.items()
            if key in userkeys]
        hashes = dict([(frame.HashKey, frame) for frame in frames])
        toremove = [z for z in self._originaltags if z in audio
                    and not (z in hashes or z.startswith('APIC'))]
        audio.update(hashes)

        images = [z for z in audio if z.startswith(u'APIC')]
        if self._images:
            newimages = []
            for image in self._images:
                i = 0
                while image.HashKey in newimages:
                    i += 1
                    image.desc += u' '*i #Pad with spaces so that each key is unique.
                audio[image.HashKey] = image
                newimages.append(image.HashKey)
            [toremove.append(z) for z in images if z not in newimages]
        else:
            toremove.extend(images)

        #pdb.set_trace()
        for z in set(toremove):
            try:
                del(audio[z])
            except KeyError:
                continue
        #pdb.set_trace()

        audio.tags.filename = self.filepath
        audio.tags.save(v1=v1_option)
        self._originaltags = audio.keys()

    @setdeco
    def __setitem__(self,key,value):
        if key in READONLY:
            return
        elif not isinstance(key, basestring):
            self._tags[key] = value
            return
        elif key == '__image':
            self.images = value
            return
        elif key in FILETAGS:
            setattr(self, self._hash[key], value)
            return

        if key not in INFOTAGS and isempty(value):
            del(self[key])
            return

        if isinstance(value, (basestring, int, long)):
            if isinstance(value, str):
                value = [unicode(value, 'utf8')]
            elif not isinstance(value, unicode):
                value = [unicode(value)]
            else:
                value = [value]
        else:
            value = [unicode(z, 'utf8') if isinstance(z, str)
                else z for z in value]

        if key in self._tags:
            self._tags[key].set_value(value)
        else:
            if key in write_frames:
                self._tags.update(write_frames[key](value))
            elif key == u'comment':
                frame = {'comment': create_comment('', value)['comment:']}
                self._tags.update(frame)
            elif key.startswith('comment:'):
                self._tags.update(create_comment(key[len('comment:'):], value))
            elif key.startswith('www:'):
                self._tags.update(create_userurl(key, value))
            elif key.startswith('ufid:'):
                self._tags.update(create_ufid(key, value))
            else:
                self._tags.update(create_usertext(key, value))


filetype = [PuddleID3FileType, Tag, 'ID3']