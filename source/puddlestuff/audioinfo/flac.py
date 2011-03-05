# -*- coding: utf-8 -*-

from mutagen.flac import FLAC
import ogg

class Tag(ogg.vorbis_tag(FLAC, 'FLAC')):
    def _info(self):
        info = self._mutfile.info
        fileinfo = [('Path', self[PATH]),
                    ('Size', str_filesize(int(self.size))),
                    ('Filename', self[FILENAME]),
                    ('Modified', self.modified)]

        ogginfo = [('Bitrate', 'Lossless'),
                ('Frequency', self.frequency),
                ('Bits Per Sample', self.bitspersample),
                ('Channels', unicode(info.channels)),
                ('Length', self.length)]
        return [('File', fileinfo), ('FLAC Info', ogginfo)]

    info = property(_info)

filetype = (FLAC, Tag, 'VorbisComment')