import struct

from mutagen.asf import ASF, ASFBoolAttribute, ASFByteArrayAttribute, ASFUnicodeAttribute

from . import tag_versions
from . import util
from .util import (usertags, PATH,
                   FILENAME, isempty, getdeco, setdeco, str_filesize, fn_hash, cover_info,
                   get_mime, unicode_list, CaselessDict, keys_deco,
                   del_deco, get_total, set_total, info_to_dict, parse_image, FieldNameError,
                   LYRICS_PREFIX)

ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
              'modified', 'filetype')

# WMA's names for fields before they matched the other formats'; writing
# them still sets these.
OLD_NAMES = {'album_subtitle': 'setsubtitle', 'comment:': 'comment', 'encodersettings': 'encodingsettings',
             'engineer': 'producer', 'label': 'organization', 'lyrics': 'unsyncedlyrics',
             'originalfilename': 'filename', 'originallyricist': 'author', 'remixer': 'arranger',
             'subtitle': 'version', 'wwwaudiosource': 'wwwsource'}

# Attributes that are true or false: they read 1 or 0, as the other formats'
# flags do, and 1 or Yes turns one on.
FLAGS = {'WM/IsCompilation'}


def get_flag(attribute):
    return '1' if str(attribute.value).strip().lower() in ('1', 'true') else '0'


def set_flag(value):
    return ASFBoolAttribute(value.strip().lower() in ('1', 'yes'))


# From picard
def bin_to_pic(image):
    data = image.value
    (type, size) = struct.unpack_from("<bi", data)
    pos = 5
    mime = b""
    while data[pos:pos + 2] != b"\x00\x00":
        mime += data[pos:pos + 2]
        pos += 2
    pos += 2
    description = b""
    while data[pos:pos + 2] != b"\x00\x00":
        description += data[pos:pos + 2]
        pos += 2
    pos += 2
    image_data = data[pos:pos + size]
    return {
        util.MIMETYPE: mime.decode("utf-16-le"),
        util.DATA: image_data,
        util.IMAGETYPE: type,
        util.DESCRIPTION: description.decode("utf-16-le"),
    }


def pic_to_bin(image):
    data = image[util.DATA]
    mime = image.get(util.MIMETYPE)
    if not mime:
        mime = get_mime(data)
        if not mime:
            return
    type = image.get(util.IMAGETYPE, 3)
    description = image.get(util.DESCRIPTION, '')
    tag_data = struct.pack("<bi", type, len(data))
    tag_data += mime.encode("utf-16-le") + b"\x00\x00"
    tag_data += description.encode("utf-16-le") + b"\x00\x00"
    tag_data += data
    return ASFByteArrayAttribute(tag_data)


class Tag(util.MockTag):
    IMAGETAGS = (util.MIMETYPE, util.DATA, util.IMAGETYPE, util.DESCRIPTION)
    mapping = {}
    revmapping = {}

    __rtranslate = {
        'album': 'WM/AlbumTitle',
        'albumartist': 'WM/AlbumArtist',
        'albumartistsortorder': 'WM/AlbumArtistSortOrder',
        'albumsortorder': 'WM/AlbumSortOrder',
        'arranger': 'WM/ModifiedBy',
        'artist': 'Author',
        'author': 'WM/OriginalLyricist',
        'bpm': 'WM/BeatsPerMinute',
        'comment': 'Description',
        'composer': 'WM/Composer',
        'conductor': 'WM/Conductor',
        'copyright': 'WM/Copyright',
        'discnumber': 'WM/PartOfSet',
        'encodedby': 'WM/EncodedBy',
        'encodingsettings': 'WM/EncodingSettings',
        'encodingtime': 'WM/EncodingTime',
        'filename': 'WM/OriginalFilename',
        'genre': 'WM/Genre',
        'grouping': 'WM/ContentGroupDescription',
        'initialkey': 'WM/InitialKey',
        'isrc': 'WM/ISRC',
        'itunescompilationflag': 'WM/IsCompilation',
        'itunescomposersortorder': 'WM/ComposerSortOrder',
        'language': 'WM/Language',
        'lyricist': 'WM/Writer',
        'mbrainz_album_id': 'MusicBrainz/Album Id',
        'mbrainz_albumartist_id': 'MusicBrainz/Album Artist Id',
        'mbrainz_artist_id': 'MusicBrainz/Artist Id',
        'mbrainz_discid': 'MusicBrainz/Disc Id',
        'mbrainz_track_id': 'MusicBrainz/Track Id',
        'mbrainz_trmid': 'MusicBrainz/TRM Id',
        'mood': 'WM/Mood',
        'musicip_puid': 'MusicIP/PUID',
        'organization': 'WM/Publisher',
        'originalalbum': 'WM/OriginalAlbumTitle',
        'originalartist': 'WM/OriginalArtist',
        'originalyear': 'WM/OriginalReleaseYear',
        'performersortorder': 'WM/ArtistSortOrder',
        'producer': 'WM/Producer',
        'releasecountry': 'MusicBrainz/Album Release Country',
        'releasestatus': 'MusicBrainz/Album Status',
        'releasetype': 'MusicBrainz/Album Type',
        'setsubtitle': 'WM/SetSubTitle',
        'title': 'Title',
        'titlesortorder': 'WM/TitleSortOrder',
        'track': 'WM/TrackNumber',
        'unsyncedlyrics': 'WM/Lyrics',
        'version': 'WM/SubTitle',
        'wwwartist': 'WM/AuthorURL',
        'wwwcommercialinfo': 'WM/PromotionURL',
        'wwwcopyright': 'CopyrightURL',
        'wwwsource': 'WM/AudioSourceURL',
        'year': 'WM/Year',
    }
    __translate = dict([(v, k) for k, v in __rtranslate.items()])

    def __init__(self, filename=None):
        self.__images = []
        self.__tags = CaselessDict()

        util.MockTag.__init__(self, filename)

    def __shown(self, name, values):
        """Whether puddletag shows the attribute as a field, so that a save
        may remove it. The others, attributes with a / in their name it
        doesn't map (WM/Provider) and those not text, are kept as they are,
        except WM/Picture, the covers."""
        return name in self.__translate or (
            '/' not in name and isinstance(values[0], ASFUnicodeAttribute))

    @property
    def filepath(self):
        return util.MockTag.get_filepath(self)

    @filepath.setter
    def filepath(self, val):
        self.__tags.update(util.MockTag.set_filepath(self, val))

    @property
    def images(self):
        return self.__images

    @images.setter
    def images(self, images):
        if images:
            self.__images = list(map(parse_image, images))
        else:
            self.__images = []
        cover_info(images, self.__tags)

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

    @getdeco
    def __getitem__(self, key):
        if key == '__image':
            return self.images
        elif key == '__total':
            return get_total(self)
        return self.__tags[key]

    @setdeco
    def __setitem__(self, key, value):
        key = OLD_NAMES.get(key, key)
        if key.startswith('__'):

            if key == '__image':
                self.images = value
            elif key in fn_hash:
                setattr(self, fn_hash[key], value)
            elif key == '__total' and 'track' in self:
                if set_total(self, value):
                    return
            return
        elif isempty(value):
            if key in self:
                del (self[key])
        elif key == 'unsyncedlyrics':
            self.__tags[key] = [LYRICS_PREFIX.sub('', text) for text in unicode_list(value)]
        else:
            self.__tags[key] = unicode_list(value)

    @del_deco
    def __delitem__(self, key):
        if key == '__image':
            self.images = []
        elif key.startswith('__'):
            return
        else:
            del (self.__tags[key])

    def delete(self):
        self.mut_obj.clear()
        for key in self.usertags:
            del (self.__tags[self.revmapping.get(key, key)])
        self.images = []
        self.save()

    @property
    def info(self):
        info = self.mut_obj.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]

        wmainfo = [('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Channels', str(info.channels)),
                   ('Length', self.length)]
        return [('File', fileinfo), ('ASF Info', wmainfo)]

    @keys_deco
    def keys(self):
        return list(self.__tags.keys())

    def link(self, filename):
        """Links the audio, filename
        returns self if successful, None otherwise."""

        self.images = None
        tags, audio = self.load(filename, ASF)
        if audio is None:
            return

        for name, values in audio.tags.items():
            if name in FLAGS:
                self.__tags[self.__translate[name]] = list(map(get_flag, values))
            elif name in self.__translate:
                self.__tags[self.__translate[name]] = list(map(str, values))
            elif self.__shown(name, values) and name not in self.__tags:
                self.__tags[name] = list(map(str, values))

        if 'WM/Picture' in audio:
            self.images = list(map(bin_to_pic, audio['WM/Picture']))

        self.__tags.update(info_to_dict(audio.info))
        self.__tags.update(tags)
        self.__tags['__filetype'] = 'ASF'
        self.filetype = 'ASF'
        self.__tags['__tag_read'] = 'ASF'
        self.set_attrs(ATTRIBUTES)
        self.mut_obj = audio
        self.update_tag_list()
        return self

    def save(self):
        """Writes the tags in self.__tags
        to self.filename if no filename is specified."""
        filepath = self.filepath

        if self.mut_obj.tags is None:
            self.mut_obj.add_tags()
        if filepath != self.mut_obj.filename:
            self.mut_obj.filename = filepath
        audio = self.mut_obj

        newtag = {}
        for field, value in usertags(self.__tags).items():
            try:
                name = self.__rtranslate[field.lower()]
                newtag[name] = list(map(set_flag, value)) if name in FLAGS else value
            except KeyError:
                if '/' in field:  # as WMA's own attributes have: it wouldn't show again
                    raise FieldNameError(field, 'WMA', filepath)
                newtag[field] = value

        pics = list(map(pic_to_bin, self.images))
        if pics:
            newtag['WM/Picture'] = pics

        toremove = [z for z in audio if z not in newtag
                    and (z == 'WM/Picture' or self.__shown(z, audio[z]))]
        for z in toremove:
            del (audio[z])
        audio.update(newtag)
        audio.save()

    def update_tag_list(self):
        self.__tags['__tag'] = 'ASF'


filetype = (ASF, Tag, 'WMA', ['wma', 'wmv'])
