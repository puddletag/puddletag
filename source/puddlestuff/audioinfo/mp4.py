# -*- coding: utf-8 -*-

import util, imghdr, pdb
from util import (usertags, strlength, strbitrate, READONLY, isempty,
    getfilename, strfrequency, getinfo, FILENAME, PATH,
    INFOTAGS, getdeco, setdeco, EXTENSION, DIRPATH,
    FILETAGS, str_filesize, DIRNAME, fn_hash, CaselessDict, keys_deco,
    del_deco, cover_info, info_to_dict, parse_image)
from copy import copy, deepcopy
from mutagen.mp4 import MP4,  MP4Cover
ATTRIBUTES = ('frequency', 'bitrate', 'length', 'accessed', 'size', 'created',
    'modified', 'bitspersample', 'channels')
import tag_versions

#mp4 tags, like id3 can only have a fixed number of tags. The ones on the left
#with the corresponding tag as recognized by puddletag on the right...

TAGS = {
    '\xa9nam': 'title',
    '\xa9alb': 'album',
    '\xa9ART': 'artist',
    'aART': 'albumartist',
    '\xa9wrt': 'composer',
    '\xa9day': 'year',
    '\xa9cmt': 'comment',
    'desc': 'description',
    'purd': 'purchasedate',
    '\xa9grp': 'grouping',
    '\xa9gen': 'genre',
    '\xa9lyr': 'lyrics',
    'purl': 'podcasturl',
    'egid': 'podcastepisodeguid',
    'catg': 'podcastcategory',
    'keyw': 'podcastkeywords',
    '\xa9too': 'encodedby',
    'cprt': 'copyright',
    'soal': 'albumsortorder',
    'soaa': 'albumartistsortorder',
    'soar': 'artistsortorder',
    'sonm': 'titlesortorder',
    'soco': 'composersortorder',
    'sosn': 'showsortorder',
    'tvsh': 'showname',
    'cpil': 'partofcompilation',
    'pgap': 'partofgaplessalbum',
    'pcst': 'podcast',
    'tmpo': 'bpm'}

REVTAGS = dict([reversed(z) for z in TAGS.items()])

#Because these values are storted in different ways, text for album, tuple
#for tracks, I created to a bunch of functions, to handle the reading
#and writing of these.

#Functions are in get and set pairs.
#get functions take a value mutagen expects it and returns it in puddletag's format.
#set functions do the opposite.

encode = lambda x: [z.encode('utf8') for z in x]

def getbool(value):
    if value:
        return [u'Yes']
    else:
        return [u'No']

def setbool(value):
    if value == 'No':
        return False
    elif value:
        return True
    else:
        return False

def settext(text):
    if isinstance(text, str):
        return [unicode(text)]
    elif isinstance(text, unicode):
        return [text]
    else:
        return [unicode(z) for z in text]

def gettext(value):
    return value

def settuple(value):
    temp = []
    for tup in value:
        if isinstance(tup, basestring):
            values = [z.strip() for z in tup.split(u'/')]
            try:
                temp.append(tuple([int(z) for z in values][:2]))
            except (TypeError, IndexError):
                continue
        else:
            temp.append(tup)
    return temp

def gettuple(value):
    return [unicode(track) + u'/' + unicode(total) for track, total in value]

def getint(value):
    return [unicode(z) for z in value]

def setint(value):
    if isinstance(value, (int, long, basestring)):
        return [int(value)]
    temp = []
    for z in value:
        try:
            temp.append(int(z))
        except ValueError:
            continue
    return temp

FUNCS = {
    'title': (gettext, settext),
    'album': (gettext, settext),
    'artist': (gettext, settext),
    'albumartist': (gettext, settext),
    'composer': (gettext, settext),
    'year': (gettext, settext),
    'comment': (gettext, settext),
    'description': (gettext, settext),
    'purchasedate': (gettext, settext),
    'grouping': (gettext, settext),
    'genre': (gettext, settext),
    'lyrics': (gettext, settext),
    'podcastURL': (gettext, settext),
    'podcastepisodeGUID': (gettext, settext),
    'podcastcategory': (gettext, settext),
    'podcastkeywords': (gettext, settext),
    'encodedby': (gettext, settext),
    'copyright': (gettext, settext),
    'albumsortorder': (gettext, settext),
    'albumartistsortorder': (gettext, settext),
    'artistsortorder': (gettext, settext),
    'titlesortorder': (gettext, settext),
    'composersortorder': (gettext, settext),
    'showsortorder': (gettext, settext),
    'showname': (gettext, settext),
    'partofcompilation': (getbool, setbool),
    'partofgaplessalbum': (getbool, setbool),
    'podcast': (getbool, setbool),
    'track': (getint, setint),
    'disc': (getint, setint),
    'totaltracks': (getint, setint),
    'totaldiscs': (getint, setint),
    'bpm': (getint, setint)}

def bin_to_pic(cover):
    try:
        format = cover.imageformat
    except AttributeError:
        format = cover.format
    if format == MP4Cover.FORMAT_PNG:
        return {'data': cover, 'mime': 'image/png'}
    else:
        return {'data': cover, 'mime': 'image/jpeg'}

def pic_to_bin(image):
    data = image[util.DATA]
    mime = imghdr.what(None, data)
    if mime == 'png':
        format = MP4Cover.FORMAT_PNG
    elif mime == 'jpeg':
        format = MP4Cover.FORMAT_JPEG
    else:
        return
    return MP4Cover(data, format)

class Tag(util.MockTag):
    """Class for AAC tags."""

    mapping = {}
    revmapping = {}
    IMAGETAGS = (util.MIMETYPE, util.DATA)

    def __init__(self, filename=None):
        self.__images = []
        self.__errors = set()
        self.__tags = CaselessDict()

        util.MockTag.__init__(self, filename)

    def get_filepath(self):
        return util.MockTag.get_filepath(self)

    def set_filepath(self,  val):
        self.__tags.update(util.MockTag.set_filepath(self, val))

    filepath = property(get_filepath, set_filepath)

    def __contains__(self, key):
        if self.revmapping:
            key = self.revmapping.get(key, key)
        return key in self.__tags

    @del_deco
    def __delitem__(self, key):
        if key == '__image':
            self.images = []  
        elif key.startswith('__'):
            return
        else:
            del(self.__tags[key])

    @getdeco
    def __getitem__(self, key):
        if key.startswith('__'):
            if key == '__image':
                return self.images
            elif key == '__total':
                return FUNCS['totaltracks'][0](self.__tags['totaltracks'])
            else:
                return self.__tags[key]

        try:
            return FUNCS[key][0](self.__tags[key])
        except KeyError:
            return gettext(self.__tags[key])

    @setdeco
    def __setitem__(self, key, value):
        if isinstance(key, (int, long)):
            self.__tags[key] = value
            return
        elif key.startswith('__'):
            if key == '__image':
                self.images = value
            if key in FILETAGS:
                setattr(self, fn_hash[key], value)
            elif key == '__total':
                self.__tags['totaltracks'] = FUNCS['totaltracks'][1](value)
            return
        elif isempty(value):
            if key in self:
                del(self[key])
            return
        else:
            try:
                self.__tags[key] = FUNCS[key][1](value)
            except KeyError:
                #User defined tags.
                self.__freeform[key] = '----:com.apple.iTunes:%s' % key
                self.__tags[key] = settext(value)
            except ValueError:
                pass

    def delete(self):
        self.mut_obj.delete()
        for z in self.usertags:
            del(self.__tags[self.revmapping.get(z, z)])
        self.images = []

    def _set_images(self, images):
        if images:
            self.__images = map(lambda i: parse_image(i, self.IMAGETAGS),
                images)
        else:
            self.__images = []
        cover_info(images, self.__tags)

    def _get_images(self):
        return self.__images

    images = property(_get_images, _set_images)

    def _info(self):
        info = self.mut_obj.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]

        mp4info = [('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Channels', unicode(info.channels)),
                   ('Length', self.length),
                   ('Bits per sample', unicode(info.bits_per_sample))]

        return [('File', fileinfo), ('MP4 Info', mp4info)]

    info = property(_info)

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""

        tags, audio = self.load(filename, MP4)

        if audio is None:
            return

        revmap, mapping = self.revmapping, self.mapping
        self.revmapping, self.mapping = {}, {}

        self.__freeform = {} #Keys are tags as required by mutagen i.e. The '----'
                            #frames. Values are the tag as represented by puddletag.

        if audio.tags: #Not empty
            keys = audio.keys()
            try:
                self.images = map(bin_to_pic, audio['covr'])
                keys.remove('covr')
            except KeyError:
                pass

            #I want 'trkn', to split into track and totaltracks, like Mp3tag.
            if 'trkn' in keys:
                self['track'] = [z[0] for z in audio['trkn']]
                self['totaltracks'] = [z[1] for z in audio['trkn']]
                keys.remove('trkn')

            #Same as above
            if 'disk' in keys:
                self['disc'] = [z[0] for z in audio['disk']]
                self['totaldiscs'] = [z[1] for z in audio['disk']]
                keys.remove('disk')

            for key in keys:
                if key in TAGS:
                    self[TAGS[key]] = audio[key]
                else:
                    tag = key[key.find(':', key.find(':') +1) + 1:]
                    self.__freeform[tag] = key
                    try:
                        self.__tags[tag] = [unicode(v, 'utf8') for v in audio[key]]
                    except UnicodeDecodeError:
                        self.__errors.add(tag)

        self.__tags.update(info_to_dict(audio.info))
        self.revmapping, self.mapping = revmap, mapping
        self.__tags['__tag_read'] = u'MP4'
        self.__tags.update(tags)
        self.filetype = 'MP4'
        self.__tags['__filetype'] = self.filetype
        self.set_attrs(ATTRIBUTES, self.__tags)
        self.update_tag_list()
        self.mut_obj = audio

    @keys_deco
    def keys(self):
        return self.__tags.keys()

    def save(self):
        if self.mut_obj.tags is None:
            self.mut_obj.add_tags()
        if self.filepath != self.mut_obj.filename:
            self.mut_obj.filename = self.filepath
        audio = self.mut_obj

        newtag = {}
        tuples = (('track', ['trkn', 'totaltracks']),
            ('disc', ['disk', 'totaldiscs']))
        tags = self.__tags
        for tag, values in tuples:
            if tag in tags:
                denom = tags[tag]
                if values[1] in tags:
                    total = tags[values[1]]
                    newtag[values[0]] = [(int(t), int(total)) for t, total in
                        zip(denom, total)]
                else:
                    newtag[values[0]] = [(int(z), 0) for z in denom]
            elif values[1] in tags:
                total = tags[values[1]]
                newtag[values[0]] = [(0, int(z)) for z in total]

        tags = usertags(self.__tags)
        tags = [(z, tags[z]) for z in tags
            if z not in ['track', 'totaltracks', 'disc', 'totaldiscs']]

        for tag, value in tags:
            try:
                newtag[REVTAGS[tag]] = value
            except KeyError:
                newtag[self.__freeform[tag].encode('utf8')] = encode(self.__tags[tag])

        if self.images:
            newtag['covr'] = map(pic_to_bin, self.images)

        toremove = [z for z in audio.keys() if
            z not in newtag and z not in self.__errors]
        for key in toremove:
            del(audio[key])
        audio.update(newtag)
        audio.save()

    def update_tag_list(self):
        l = tag_versions.tags_in_file(self.filepath)
        if l:
            self.__tags['__tag'] = u'MP4, ' + u', '.join(l)
        else:
            self.__tags['__tag'] = u'MP4'

filetype = (MP4, Tag, 'MP4', ['m4a', 'mp4', 'm4v'])