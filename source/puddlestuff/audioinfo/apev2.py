# -*- coding: utf-8 -*-

from mutagen.apev2 import APEv2File, APEBinaryValue
import util, pdb
from util import (strlength, strbitrate, strfrequency, usertags, PATH, isempty,
    getfilename, lnglength, getinfo, FILENAME, INFOTAGS, READONLY, DIRNAME,
    FILETAGS, DIRPATH, EXTENSION, getdeco, setdeco, str_filesize)
ATTRIBUTES = ('length', 'accessed', 'size', 'created',
    'modified', 'filetype')
import imghdr
from mutagen.apev2 import APEValue, BINARY

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
        _hash = {PATH: 'filepath',
            FILENAME:'filename',
            EXTENSION: 'ext',
            DIRPATH: 'dirpath',
            DIRNAME: 'dirname'}

        def _getImages(self):
            return self._images

        def _setImages(self, images):
            self._images = images

        images = property(_getImages, _setImages)

        @getdeco
        def __getitem__(self,key):
            if key == '__image':
                return self.images
            return self._tags[key]

        @setdeco
        def __setitem__(self, key, value):
            
            if key == '__image':
                self.images = value
                return

            if isinstance(key, (int, long)):
                self._tags[key] = value
                return
            elif key in READONLY:
                return
            elif key in FILETAGS:
                setattr(self, self._hash[key], value)
                return
            elif key in INFOTAGS:
                self._tags[key] = value
                return
            elif key not in INFOTAGS and isempty(value):
                del(self[key])
                return


            if (key not in INFOTAGS) and isinstance(value, (basestring, int, long)):
                self._tags[key] = [unicode(value)]
            else:
                self._tags[key] = [z if isinstance(z, unicode)
                    else unicode(z) for z in value]

        def copy(self):
            tag = Tag()
            tag.load(copy(self._mutfile), self._tags.copy())
            return tag

        def delete(self):
            self._mutfile.delete()
            for z in self.usertags:
                del(self._tags[z])

        def _info(self):
            info = self._mutfile.info
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

        def load(self, mutfile, tags):
            self._mutfile = mutfile
            self.filepath = tags.filepath
            self._tags = tags

        def link(self, filename, x = None):
            """Links the audio, filename
            returns self if successful, None otherwise."""
            self._images = []
            try:
                tags, audio = self._init_info(filename, mutagen_file)
            except mutagen.apev2.APENoHeaderError:
                audio = mutagen_file()
                tags, audio = self._init_info(filename, None)
                audio.filename = tags['__filepath']

            if audio is None:
                return

            
            for key in audio:
                try:
                    if key.lower() in COVER_KEYS:
                        img_type = COVER_KEYS.get(key.lower(), 3)
                        self._images.append(
                            bin_to_pic(audio[key].value, img_type))
                    else:
                        self._tags[key.lower()] = audio.tags[key][:]
                except TypeError:
                    pass

            self._tags.update(base_function(audio.info))
            self._tags.update(tags)
            self._set_attrs(attrib_fields)
            self._mutfile = audio
            return self

        def save(self):
            if self._mutfile.tags is None:
                self._mutfile.add_tags()
            if self.filepath != self._mutfile.filename:
                self._mutfile.filename = self.filepath
            audio = self._mutfile

            newtag = {}
            if self.images:
                [newtag.update(pic_to_bin(z)) for z in self.images]
            for field, value in usertags(self._tags).items():
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