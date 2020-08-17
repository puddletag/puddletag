from copy import deepcopy

from mutagen.oggvorbis import OggVorbis

try:
    from mutagen.oggopus import OggOpus
except ImportError:
    OggOpus = None

from mutagen.flac import Picture, FLAC
import base64

from . import util
from .util import (usertags, PATH,
                   FILENAME, isempty, getdeco, setdeco, str_filesize, unicode_list,
                   CaselessDict, del_deco, keys_deco, fn_hash, cover_info,
                   get_total, set_total, parse_image, info_to_dict,
                   get_mime)
from .tag_versions import tags_in_file

PICARGS = ('type', 'mime', 'desc', 'width', 'height', 'depth', 'data')

ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
              'modified', 'bitspersample')

COVER_KEY = 'metadata_block_picture'


def base64_to_image(value):
    return bin_to_image(Picture(base64.standard_b64decode(value)))


def bin_to_image(pic):
    return {'data': pic.data, 'description': pic.desc, 'mime': pic.mime,
            'imagetype': pic.type}


def image_to_base64(image):
    return base64.standard_b64encode(image_to_bin(image).write()).decode('ascii')


def image_to_bin(image):
    props = {}
    data = image[util.DATA]
    description = image.get(util.DESCRIPTION)
    if not description: description = ''

    mime = image.get(util.MIMETYPE)
    if mime is None: mime = get_mime(data)
    imagetype = image.get(util.IMAGETYPE, 3)

    props['type'] = imagetype
    props['desc'] = description
    props['mime'] = mime
    props['data'] = data

    p = Picture()
    [setattr(p, z, props[z]) for z in PICARGS if z in props]
    return p


def vorbis_tag(base, name):
    class Tag(util.MockTag):
        IMAGETAGS = (util.MIMETYPE, util.DESCRIPTION, util.DATA, util.IMAGETYPE)
        mapping = {}
        revmapping = {}

        def __init__(self, filename=None):
            self.__images = []
            self.__tags = CaselessDict()

            self.filetype = name
            self.__tags['__filetype'] = self.filetype
            self.__tags['__tag_read'] = 'VorbisComment'

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

        def __deepcopy__(self, memo):
            cls = Tag()
            cls.mapping = self.mapping
            cls.revmapping = self.revmapping
            cls.set_fundamentals(deepcopy(self.__tags),
                                 self.mut_obj, self.images)
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
                elif key == '__total':
                    set_total(self, value)
                elif key in fn_hash:
                    setattr(self, fn_hash[key], value)
            elif isempty(value):
                if key in self:
                    del (self[key])
                else:
                    return
            else:
                if isinstance(value, int):
                    self.__tags[key.lower()] = [str(value)]
                else:
                    self.__tags[key.lower()] = unicode_list(value)

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
            tags, audio = self.load(filename, base)
            if audio is None:
                return

            for key in audio:
                if key == COVER_KEY:
                    self.images = list(map(base64_to_image, audio[key]))
                else:
                    self.__tags[key.lower()] = audio.tags[key]

            if base == FLAC:
                self.images = [_f for _f in map(bin_to_image, audio.pictures) if _f]
            elif not self.images:
                self.images = []

            self.__tags.update(info_to_dict(audio.info))
            self.__tags.update(tags)
            self.set_attrs(ATTRIBUTES)
            self.mut_obj = audio
            self._originaltags = list(self.__tags.keys())
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
            for tag, value in usertags(self.__tags).items():
                newtag[tag] = value

            if self.__images:
                if base == FLAC:
                    audio.clear_pictures()
                    list(map(lambda p: audio.add_picture(image_to_bin(p)),
                             self.__images))
                else:
                    newtag[COVER_KEY] = [_f for _f in map(image_to_base64, self.__images) if _f]
            else:
                if base == FLAC:
                    audio.clear_pictures()

            toremove = [z for z in audio if z not in newtag]
            for z in toremove:
                del (audio[z])
            audio.update(newtag)
            audio.save()

        def set_fundamentals(self, tags, mut_obj, images=None):
            self.__tags = tags
            self.mut_obj = mut_obj
            if images:
                self.images = images
            else:
                self.images = []
            self._originaltags = list(tags.keys())

        def update_tag_list(self):
            l = tags_in_file(self.filepath)
            if l:
                self.__tags['__tag'] = 'VorbisComment, ' + ', '.join(l)
            else:
                self.__tags['__tag'] = 'VorbisComment'

    return Tag


class Ogg_Tag(vorbis_tag(OggVorbis, 'Ogg Vorbis')):

    def _info(self):
        info = self.mut_obj.info
        fileinfo = [
            ('Path', self[PATH]),
            ('Size', str_filesize(int(self.size))),
            ('Filename', self[FILENAME]),
            ('Modified', self.modified)]

        ogginfo = [('Bitrate', self.bitrate),
                   ('Frequency', self.frequency),
                   ('Channels', str(info.channels)),
                   ('Length', self.length)]
        return [('File', fileinfo), ('Ogg Info', ogginfo)]

    info = property(_info)


if OggOpus:
    class Opus_Tag(vorbis_tag(OggOpus, 'Ogg Opus')):
        def _info(self):
            info = self.mut_obj.info
            fileinfo = [
                ('Path', self[PATH]),
                ('Size', str_filesize(int(self.size))),
                ('Filename', self[FILENAME]),
                ('Modified', self.modified)]

            ogginfo = [('Bitrate', self.bitrate),
                       ('Channels', str(info.channels)),
                       ('Length', self.length)]
            return [('File', fileinfo), ('Opus Info', ogginfo)]

        info = property(_info)


class FLAC_Tag(vorbis_tag(FLAC, 'FLAC')):
    def _info(self):
        info = self.mut_obj.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]

        ogginfo = [('Bitrate', 'Lossless'),
                   ('Frequency', self.frequency),
                   ('Bits Per Sample', self.bitspersample),
                   ('Channels', str(info.channels)),
                   ('Length', self.length)]
        return [('File', fileinfo), ('FLAC Info', ogginfo)]

    info = property(_info)


filetypes = []

if OggOpus:
    filetypes.append((OggOpus, Opus_Tag, 'VorbisComment', 'opus.ogg'))
    filetypes.append((OggOpus, Opus_Tag, 'VorbisComment', 'opus'))

filetypes.extend([
    (OggVorbis, Ogg_Tag, 'VorbisComment', 'ogg'),
    (FLAC, FLAC_Tag, 'VorbisComment', 'flac')]
)
