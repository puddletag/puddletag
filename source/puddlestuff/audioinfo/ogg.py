# -*- coding: utf-8 -*-

from mutagen.oggvorbis import OggVorbis
import mutagen.flac
from mutagen.flac import Picture
import base64

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH,
    getfilename, lnglength, getinfo, FILENAME, INFOTAGS,
    READONLY, isempty, FILETAGS, EXTENSION, DIRPATH,
    getdeco, setdeco, str_filesize, unicode_list,
    CaselessDict, del_deco, keys_deco, fn_hash, cover_info,
    MONO, STEREO, get_total, set_total)
from tag_versions import tags_in_file
from copy import copy
PICARGS = ('type', 'mime', 'desc', 'width', 'height', 'depth', 'data')

ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
    'modified', 'bitspersample')

COVER_KEY = 'metadata_block_picture'

def base64_to_image(value):
    return bin_to_image(mutagen.flac.Picture(base64.standard_b64decode(value)))

def bin_to_image(pic):
    return {'data': pic.data, 'description': pic.desc, 'mime': pic.mime,
        'imagetype': pic.type}

def image_to_base64(image):
    return base64.standard_b64encode(image_to_bin(image).write())

def image_to_bin(image):
    props = {}
    data = image[util.DATA]
    description = image.get(util.DESCRIPTION)
    if not description: description = u''

    mime = image.get(util.MIMETYPE)
    if mime is None: mime = get_mime(data)
    imagetype = image.get(util.IMAGETYPE, 3)

    props['type'] = imagetype
    props['desc'] = description
    props['mime'] = mime
    props['data'] = data

    args = dict([(z, props[z]) for z in PICARGS if z in props])
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

            util.MockTag.__init__(self, filename)

        def get_filepath(self):
            return util.MockTag.get_filepath(self)

        def set_filepath(self,  val):
            self.__tags.update(util.MockTag.set_filepath(self, val))

        filepath = property(get_filepath, set_filepath)

        def _getImages(self):
            return self.__images

        def _setImages(self, images):
            if images:
                self.__images = images
            else:
                self.__images = []
            cover_info(images, self.__tags)

        images = property(_getImages, _setImages)

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
                    del(self[key])
                else:
                    return
            else:
                if isinstance(value, (int, long)):
                    self.__tags[key.lower()] = [unicode(value)]
                else:
                    self.__tags[key.lower()] = unicode_list(value)
                
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

        def delete(self):
            self.mut_obj.delete()
            for z in self.usertags:
                del(self[z])
            self.images = []
            self.save()

        @keys_deco
        def keys(self):
            return self.__tags.keys()

        def link(self, filename):
            """Links the audio, filename
            returns self if successful, None otherwise."""
            self.__images = []
            tags, audio = self.load(filename, base)
            if audio is None:
                return

            for key in audio:
                if key == COVER_KEY:
                    self.images = map(base64_to_image, audio[key])
                else:
                    self.__tags[key.lower()] = audio.tags[key]

            if base == mutagen.flac.FLAC:
                self.images = map(bin_to_image, audio.pictures)

            info = audio.info
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

            try: tags['__mode'] = MONO if info.channels == 1 else STEREO
            except AttributeError: pass

            self.__tags.update(tags)
            self.set_attrs(ATTRIBUTES)
            self.mut_obj = audio
            self._originaltags = self.__tags.keys()
            self.filetype = name
            self.__tags['__filetype'] = self.filetype
            self.__tags['__tag_read'] = u'VorbisComment'
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
                if base == mutagen.flac.FLAC:
                    audio.clear_pictures()
                    map(lambda p: audio.add_picture(image_to_bin(p)),
                        self.__images)
                else:
                    newtag[COVER_KEY] = map(image_to_base64, self.__images)
            else:
                if base == mutagen.flac.FLAC:
                    audio.clear_pictures()

            toremove = [z for z in audio if z not in newtag]
            for z in toremove:
                del(audio[z])
            audio.update(newtag)
            audio.save()

        def update_tag_list(self):
            l = tags_in_file(self.filepath)
            if l:
                self.__tags['__tag'] = u'VorbisComment, ' + u', '.join(l)
            else:
                self.__tags['__tag'] = u'VorbisComment'
    return Tag

class Tag(vorbis_tag(OggVorbis, 'Ogg Vorbis')):

    def _info(self):
        info = self.mut_obj.info
        fileinfo = [
            ('Path', self[PATH]),
            ('Size', str_filesize(int(self.size))),
            ('Filename', self[FILENAME]),
            ('Modified', self.modified)]

        ogginfo = [('Bitrate', self.bitrate),
                ('Frequency', self.frequency),
                ('Channels', unicode(info.channels)),
                ('Length', self.length)]
        return [('File', fileinfo), ('Ogg Info', ogginfo)]

    info = property(_info)

filetype = (OggVorbis, Tag, 'VorbisComment')
