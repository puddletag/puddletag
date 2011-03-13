# -*- coding: utf-8 -*-

from mutagen.apev2 import APEv2File, APEBinaryValue
import util, pdb
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
    getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY, DIRNAME,
    FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize, fn_hash,
    keys_deco, del_deco, CaselessDict, unicode_list, cover_info)
ATTRIBUTES = ('length', 'accessed', 'size', 'created',
    'modified', 'filetype')
import imghdr
from mutagen.apev2 import APEValue, BINARY, APENoHeaderError
import tag_versions

COVER_KEYS = {'cover art (front)': 3, 'cover art (back)': 4}

def get_pics(tag):
    keys = dict((key.lower(), key) for key in tag)

    pics = []

    for key in cover_keys:
        if key in keys:
            pics.append(parse_pic(tag[keys[key]].value, cover_keys[key]))

    return pics

def bin_to_pic(value, covertype = 3):
    ret = {}
    start = value.find('\x00')
    ret[util.DESCRIPTION] = value[:start].decode('utf8', 'replace')

    ret[util.DATA] = value[start + 1:]

    mime = imghdr.what(None, ret['data'])
    if mime:
        ret[util.MIMETYPE] = u'image/' + mime
    ret[util.IMAGETYPE] = covertype

    return ret

def pic_to_bin(pic):
    desc = pic[util.DESCRIPTION].encode('utf8')
    data = pic[util.DATA]
    covertype = pic[util.IMAGETYPE]

    key = 'Cover Art (Back)' if covertype == 4 else 'Cover Art (Front)'

    return {key: APEValue(''.join((desc, '\x00', data)), BINARY)}

def get_class(mutagen_file, base_function, attrib_fields):
    class Tag(util.MockTag):
        """Tag class for APEv2 files.

        Tags are used as in ogg.py"""
        IMAGETAGS = (util.MIMETYPE, util.DESCRIPTION, util.DATA, util.IMAGETYPE)
        mapping = {}
        revmapping = {}
        apev2=True

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
        def __getitem__(self,key):
            if key == '__image':
                return self.images
            elif key == '__total' and 'track' in self:
                try:
                    return self['track'][0].split(u'/')[1].strip()
                except IndexError:
                    pass
            return self.__tags[key]

        @setdeco
        def __setitem__(self, key, value):
            
            if key == '__image':
                self.images = value
                return

            if key.startswith('__'):
                if key == '__image':
                    self.images = value
                elif key in fn_hash:
                    setattr(self, fn_hash[key], value)
                return
            elif isempty(value):
                if key in self:
                    del(self[key])
            else:
                value = unicode_list(value)
                if isempty(value): return
                self.__tags[key] = value

        def delete(self):
            self.mut_obj.delete()
            for z in self.usertags:
                del(self.__tags[z])

        def _info(self):
            info = self.mut_obj.info
            fileinfo = [('Path', self[PATH]),
                        ('Size', str_filesize(int(self.size))),
                        ('Filename', self[FILENAME]),
                        ('Modified', self.modified)]
            apeinfo = [('Length', self.length)]
            attr = {
                'Channels': 'channels',
                'Version': 'version'}
            for k, v in attr.items():
                try:
                    apeinfo.append([k, unicode(getattr(info, v))])
                except AttributeError:
                    continue
            return [('File', fileinfo), ("%s Info" % self.filetype, apeinfo)]

        info = property(_info)

        @keys_deco
        def keys(self):
            return self.__tags.keys()

        def link(self, filename, x = None):
            """Links the audio, filename
            returns self if successful, None otherwise."""
            self.__images = []
            try:
                tags, audio = self.load(filename, mutagen_file)
            except APENoHeaderError:
                audio = mutagen_file()
                tags, audio = self._init_info(filename, None)
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
            self.__tags.update(base_function(audio.info))
            self.__tags.update(tags)
            self.__tags['__tag_read'] = u'APEv2'
            self.set_attrs(attrib_fields)
            self.filetype = 'APEv2' if '__filetype' not in self.__tags else \
                self.__tags['__filetype']
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
                    if isinstance(field, unicode):
                        field = field.encode('utf8')
                    newtag[field] = value
                except AttributeError:
                    pass
            toremove = [z for z in audio if z not in newtag and audio[z].kind == 0]
            for z in toremove:
                del(audio[z])
            audio.tags.update(newtag)
            audio.save()

        def update_tag_list(self):
            l = tag_versions.tags_in_file(self.filepath,
                [tag_versions.ID3_V1, tag_versions.ID3_V2])
            if l:
                self.__tags['__tag'] = u'APEv2, ' + u', '.join(l)
            else:
                self.__tags['__tag'] = u'APEv2'

    return Tag

def base_tags(info):
    tags = {'__filetype': 'APEv2',
        u"__length": strlength(info.length)}
    if hasattr(info, 'sample_rate'):
        tags.update(
            {u"__frequency": strfrequency(info.sample_rate)})
    return tags

Tag = get_class(APEv2File, base_tags, ATTRIBUTES)

filetype = (APEv2File, Tag , u'APEv2')