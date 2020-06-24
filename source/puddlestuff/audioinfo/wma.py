import struct

from mutagen.asf import ASF, ASFByteArrayAttribute, ASFUnicodeAttribute

from . import tag_versions
from . import util
from .util import (usertags, PATH,
                   FILENAME, isempty, getdeco, setdeco, str_filesize, fn_hash, cover_info,
                   get_mime, unicode_list, CaselessDict, keys_deco,
                   del_deco, get_total, set_total, info_to_dict, parse_image)

ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
              'modified', 'filetype')


# From picard
def bin_to_pic(image):
    data = image.value
    (type, size) = struct.unpack_from("<bi", data)
    pos = 5
    mime = ""
    while data[pos:pos + 2] != "\x00\x00":
        mime += data[pos:pos + 2]
        pos += 2
    pos += 2
    description = ""
    while data[pos:pos + 2] != "\x00\x00":
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
    tag_data += mime.encode("utf-16-le") + "\x00\x00"
    tag_data += description.encode("utf-16-le") + "\x00\x00"
    tag_data += data
    return ASFByteArrayAttribute(tag_data)


class Tag(util.MockTag):
    IMAGETAGS = (util.MIMETYPE, util.DATA, util.IMAGETYPE, util.DESCRIPTION)
    mapping = {}
    revmapping = {}

    __rtranslate = {
        'album': 'WM/AlbumTitle',
        'album_subtitle': 'WM/SetSubTitle',
        'albumartist': 'WM/AlbumArtist',
        'albumartistsortorder': 'WM/AlbumArtistSortOrder',
        'albumsortorder': 'WM/AlbumSortOrder',
        'artist': 'Author',
        'bpm': 'WM/BeatsPerMinute',
        'comment:': 'Description',
        'composer': 'WM/Composer',
        'conductor': 'WM/Conductor',
        'copyright': 'WM/Copyright',
        'discnumber': 'WM/PartOfSet',
        'encodedby': 'WM/EncodedBy',
        'encodersettings': 'WM/EncodingSettings',
        'encodingtime': 'WM/EncodingTime',
        'engineer': 'WM/Producer',
        'genre': 'WM/Genre',
        'grouping': 'WM/ContentGroupDescription',
        'initialkey': 'WM/InitialKey',
        'isrc': 'WM/ISRC',
        'label': 'WM/Publisher',
        'language': 'WM/Language',
        'lyricist': 'WM/Writer',
        'lyrics': 'WM/Lyrics',
        'mbrainz_album_id': 'MusicBrainz/Album Id',
        'mbrainz_albumartist_id': 'MusicBrainz/Album Artist Id',
        'mbrainz_artist_id': 'MusicBrainz/Artist Id',
        'mbrainz_discid': 'MusicBrainz/Disc Id',
        'mbrainz_track_id': 'MusicBrainz/Track Id',
        'mbrainz_trmid': 'MusicBrainz/TRM Id',
        'mood': 'WM/Mood',
        'musicip_puid': 'MusicIP/PUID',
        'originalalbum': 'WM/OriginalAlbumTitle',
        'originalartist': 'WM/OriginalArtist',
        'originalfilename': 'WM/OriginalFilename',
        'originallyricist': 'WM/OriginalLyricist',
        'originalyear': 'WM/OriginalReleaseYear',
        'performersortorder': 'WM/ArtistSortOrder',
        'releasecountry': 'MusicBrainz/Album Release Country',
        'releasestatus': 'MusicBrainz/Album Status',
        'releasetype': 'MusicBrainz/Album Type',
        'remixer': 'WM/ModifiedBy',
        'subtitle': 'WM/SubTitle',
        'title': 'Title',
        'titlesortorder': 'WM/TitleSortOrder',
        'track': 'WM/TrackNumber',
        'unsyncedlyrics': 'WM/Lyrics',
        'wwwartist': 'WM/AuthorURL',
        'wwwaudiosource': 'WM/AudioSourceURL',
        'wwwcommercialinfo': 'WM/PromotionURL',
        'wwwcopyright': 'CopyrightURL',
        'year': 'WM/Year',
    }
    __translate = dict([(v, k) for k, v in __rtranslate.items()])

    def __init__(self, filename=None):
        self.__images = []
        self.__tags = CaselessDict()

        util.MockTag.__init__(self, filename)

    def get_filepath(self):
        return util.MockTag.get_filepath(self)

    def set_filepath(self, val):
        self.__tags.update(util.MockTag.set_filepath(self, val))

    filepath = property(get_filepath, set_filepath)

    def _getImages(self):
        return self.__images

    def _setImages(self, images):
        if images:
            self.__images = list(map(parse_image, images))
        else:
            self.__images = []
        cover_info(images, self.__tags)

    images = property(_getImages, _setImages)

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
            del (self[key])
        elif key in self.__rtranslate:
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

    def _info(self):
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

    info = property(_info)

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
            try:
                self.__tags[self.__translate[name]] = list(map(str, values))
            except KeyError:
                if isinstance(values[0], ASFUnicodeAttribute):
                    if not '/' in name and name not in self.__tags:
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
                newtag[self.__rtranslate[field]] = value
            except KeyError:
                newtag[field] = value

        pics = list(map(pic_to_bin, self.images))
        if pics:
            newtag['WM/Picture'] = pics

        toremove = [z for z in audio if z not in newtag]
        for z in toremove:
            del (audio[z])
        audio.update(newtag)
        audio.save()

    def update_tag_list(self):
        l = tag_versions.tags_in_file(self.filepath)
        if l:
            self.__tags['__tag'] = 'ASF, ' + ', '.join(l)
        else:
            self.__tags['__tag'] = 'ASF'


filetype = (ASF, Tag, 'WMA', ['wma', 'wmv'])
