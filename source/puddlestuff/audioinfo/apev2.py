from copy import deepcopy

from mutagen.apev2 import APEv2File, APEValue, BINARY, APENoHeaderError
from mutagen.monkeysaudio import MonkeysAudio, MonkeysAudioHeaderError
from mutagen.musepack import Musepack, MusepackHeaderError
from mutagen.wavpack import WavPack, WavPackHeaderError

from . import util
from .util import (CaselessDict, FILENAME, MockTag, PATH,
                   cover_info, del_deco, fn_hash, get_mime, get_total,
                   getdeco, info_to_dict, isempty, keys_deco, parse_image, set_total,
                   setdeco, str_filesize, unicode_list, usertags)

ATTRIBUTES = ['length', 'accessed', 'size', 'created',
              'modified', 'filetype']

COVER_KEYS = {'cover art (front)': 3, 'cover art (back)': 4}


class DefaultHeaderError(RuntimeError): pass


def bin_to_pic(value, covertype=3):
    ret = {}
    start = value.find('\x00')
    ret[util.DESCRIPTION] = value[:start].decode('utf8', 'replace')

    ret[util.DATA] = value[start + 1:]

    ret[util.MIMETYPE] = get_mime(ret[util.DATA])
    ret[util.IMAGETYPE] = covertype

    return ret


def pic_to_bin(pic):
    desc = pic[util.DESCRIPTION].encode('utf8')
    data = pic[util.DATA]
    covertype = pic[util.IMAGETYPE]

    key = 'Cover Art (Back)' if covertype == 4 else 'Cover Art (Front)'

    if data:
        return {key: APEValue(''.join((desc, '\x00', data)), BINARY)}
    return {}


def get_class(mutagen_file, filetype, attrib_fields, header_error=None):
    class APEv2Base(MockTag):
        """Tag class for APEv2 files.

        Tags are used as in ogg.py"""
        IMAGETAGS = (util.MIMETYPE, util.DESCRIPTION, util.DATA, util.IMAGETYPE)
        mapping = {}
        revmapping = {}
        apev2 = True

        def __init__(self, filename=None):
            self.__images = []
            self.__tags = CaselessDict()

            MockTag.__init__(self, filename)

        def get_filepath(self):
            return MockTag.get_filepath(self)

        def set_filepath(self, val):
            self.__tags.update(MockTag.set_filepath(self, val))

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

            if key == '__image':
                self.images = value
                return

            if key.startswith('__'):
                if key == '__image':
                    self.images = value
                elif key == '__total':
                    set_total(self, value)
                elif key in fn_hash:
                    setattr(self, fn_hash[key], value)
                return
            elif isempty(value):
                if key in self:
                    del (self[key])
            else:
                value = unicode_list(value)
                if isempty(value): return
                self.__tags[key] = value

        def delete(self):
            self.mut_obj.delete()
            for key in self.usertags:
                del (self.__tags[self.revmapping.get(key, key)])
            self.images = []

        def _info(self):
            info = self.mut_obj.info
            fileinfo = [('Path', self[PATH]),
                        ('Size', str_filesize(int(self.size))),
                        ('Filename', self[FILENAME]),
                        ('Modified', self.modified)]
            apeinfo = [('Length', self.length)]
            attr = [
                ('Channels', 'channels'),
                ('Version', 'version')]
            for k, v in attr:
                try:
                    apeinfo.append([k, str(getattr(info, v))])
                except AttributeError:
                    continue
            return [('File', fileinfo), ("%s Info" % self.filetype, apeinfo)]

        info = property(_info)

        @keys_deco
        def keys(self):
            return list(self.__tags.keys())

        def link(self, filename):
            """Links the audio, filename
            returns self if successful, None otherwise."""
            no_header = DefaultHeaderError if header_error is None \
                else header_error

            self.__images = []
            try:
                tags, audio = self.load(filename, mutagen_file)
            except no_header:  # Try loading just APEv2
                tags, audio = self.load(filename, APEv2File)
            except APENoHeaderError:
                audio = mutagen_file()
                tags, audio = self.load(filename, None)
                audio.filename = tags['__filepath']

            if audio is None:
                return

            images = []
            for key in audio:
                try:
                    if key.lower() in COVER_KEYS:
                        img_type = COVER_KEYS.get(key.lower(), 3)
                        images.append(
                            bin_to_pic(audio[key].value, img_type))
                    else:
                        self.__tags[key.lower()] = audio.tags[key][:]
                except TypeError:
                    pass

            self.images = images
            self.__tags.update(info_to_dict(audio.info))
            self.__tags.update(tags)
            self.__tags['__tag_read'] = 'APEv2'
            self.set_attrs(attrib_fields)
            self.filetype = filetype
            self.__tags['__filetype'] = filetype
            self.update_tag_list()
            self.mut_obj = audio
            return self

        def save(self):
            if self.mut_obj.tags is None:
                self.mut_obj.add_tags()
            if self.filepath != self.mut_obj.filename:
                self.mut_obj.filename = self.filepath
            audio = self.mut_obj

            newtag = {}
            if self.images:
                [newtag.update(pic_to_bin(z)) for z in self.images]
            for field, value in usertags(self.__tags).items():
                try:
                    newtag[field] = value
                except AttributeError:
                    pass
            toremove = [z for z in audio if z
                        not in newtag and audio[z].kind == 0]
            for z in toremove:
                del (audio[z])
            audio.tags.update(newtag)
            audio.save()

        def set_fundamentals(self, tags, mut_obj, images=None):
            self.__tags = tags
            self.mut_obj = mut_obj
            if images:
                self.images = images
            self._originaltags = list(tags.keys())

        def update_tag_list(self):
            from . import tag_versions
            l = tag_versions.tags_in_file(self.filepath,
                                          [tag_versions.ID3_V1, tag_versions.ID3_V2])
            if l:
                self.__tags['__tag'] = 'APEv2, ' + ', '.join(l)
            else:
                self.__tags['__tag'] = 'APEv2'

    return APEv2Base


mp_base = get_class(Musepack, 'Musepack',
                    ATTRIBUTES + ['frequency', 'bitrate', 'version', 'channels'],
                    MusepackHeaderError)


class MusePackTag(mp_base):
    def _info(self):
        info = self.mut_obj.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]
        mpinfo = [('Bitrate', self.bitrate),
                  ('Frequency', self.frequency),
                  ('Channels', str(info.channels)),
                  ('Length', self.length),
                  ('Stream Version', str(info.version))]
        return [('File', fileinfo), ("Musepack Info", mpinfo)]

    info = property(_info)


ma_base = get_class(MonkeysAudio, "Monkey's Audio",
                    ATTRIBUTES + ['bitrate', 'frequency', 'version', 'channels'],
                    MonkeysAudioHeaderError)


class MonkeysAudioTag(ma_base):
    def _info(self):
        info = self.mut_obj.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]
        mainfo = [('Bitrate', 'Lossless'),
                  ('Frequency', self.frequency),
                  ('Channels', str(info.channels)),
                  ('Length', self.length),
                  ('Stream Version', str(info.version))]
        return [('File', fileinfo), ("Monkey's Audio", mainfo)]

    info = property(_info)


wv_base = get_class(WavPack, 'WavPack',
                    ATTRIBUTES + ['frequency', 'bitrate'], WavPackHeaderError)


class WavPackTag(wv_base):
    def _info(self):
        info = self.mut_obj.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]
        wpinfo = [('Frequency', self.frequency),
                  ('Channels', str(info.channels)),
                  ('Length', self.length),
                  ('Bitrate', 'Lossless')]
        return [('File', fileinfo), ("WavPack Info", wpinfo)]

    info = property(_info)


Tag = get_class(APEv2File, 'APEv2', ATTRIBUTES)

filetypes = [
    (APEv2File, Tag, 'APEv2'),
    (MonkeysAudio, MonkeysAudioTag, 'APEv2',
     ['ape', 'apl']),
    (WavPack, WavPackTag, 'APEv2', 'wv'),
    (Musepack, Tag, 'APEv2', 'mpc')]
