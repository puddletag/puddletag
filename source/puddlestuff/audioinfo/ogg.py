# -*- coding: utf-8 -*-

from mutagen.oggvorbis import OggVorbis
import mutagen.flac
from mutagen.flac import Picture
import base64

import util
from util import (strlength, strbitrate, strfrequency, usertags, PATH,
    getfilename, lnglength, getinfo, FILENAME, INFOTAGS,
    READONLY, isempty, FILETAGS, EXTENSION, DIRPATH,
    getdeco, setdeco, str_filesize)
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

        def _getImages(self):
            return self._images

        def _setImages(self, images):
            self._images = images

        images = property(_getImages, _setImages)

        @getdeco
        def __getitem__(self, key):
            if key == '__image':
                return self.images
            return self._tags[key]

        @setdeco
        def __setitem__(self, key, value):
            if key in READONLY:
                return
            elif key in FILETAGS:
                setattr(self, self._hash[key], value)
                return

            if key not in INFOTAGS and isempty(value):
                del(self[key])
            elif key == '__image':
                self.images = value
            elif key in INFOTAGS or isinstance(key, (int, long)):
                self._tags[key] = value
            elif (key not in INFOTAGS) and isinstance(value, (basestring, int, long)):
                self._tags[key.lower()] = [unicode(value)]
            else:
                self._tags[key.lower()] = [unicode(z) for z in value]

        def copy(self):
            tag = Tag()
            tag.load(copy(self._mutfile), self._tags.copy())
            return tag

        def delete(self):
            self._mutfile.delete()
            for z in self.usertags:
                del(self[z])
            self.images = []
            self.save()

        def link(self, filename):
            """Links the audio, filename
            returns self if successful, None otherwise."""
            self._images = []
            tags, audio = self._init_info(filename, base)
            if audio is None:
                return

            for key in audio:
                if key == COVER_KEY:
                    self.images = map(base64_to_image, audio[key])
                else:
                    self._tags[key.lower()] = audio.tags[key]

            if base == mutagen.flac.FLAC:
                self._images = map(bin_to_image, audio.pictures)

            info = audio.info
            try: tags[u"__frequency"] = strfrequency(info.sample_rate)
            except AttributeError: pass

            try: tags[u"__length"] = strlength(info.length)
            except AttributeError: pass

            try: tags[u"__bitrate"] = strbitrate(info.bitrate)
            except AttributeError: tags[u"__bitrate"] = u'0 kb/s'

            try: tags[u'__bitspersample'] = unicode(info.bits_per_sample)
            except AttributeError: pass

            self._tags.update(tags)
            self._set_attrs(ATTRIBUTES)
            self._mutfile = audio
            self._originaltags = self._tags.keys()
            self.filetype = name
            self._tags['__filetype'] = self.filetype
            return self

        def save(self):
            """Writes the tags in self._tags
            to self.filename if no filename is specified."""
            filepath = self.filepath

            if self._mutfile.tags is None:
                self._mutfile.add_tags()
            if filepath != self._mutfile.filename:
                self._mutfile.filename = filepath
            audio = self._mutfile

            newtag = {}
            for tag, value in usertags(self._tags).items():
                newtag[tag] = value

            if self._images:
                if base == mutagen.flac.FLAC:
                    audio.clear_pictures()
                    map(lambda p: audio.add_picture(image_to_bin(p)),
                        self._images)
                else:
                    newtag[COVER_KEY] = map(image_to_base64, self._images)
            else:
                if base == mutagen.flac.FLAC:
                    audio.clear_pictures()

            toremove = [z for z in audio if z not in newtag]
            for z in toremove:
                del(audio[z])
            audio.update(newtag)
            audio.save()
    return Tag

class Tag(vorbis_tag(OggVorbis, 'Ogg Vorbis')):

    def _info(self):
        info = self._mutfile.info
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
