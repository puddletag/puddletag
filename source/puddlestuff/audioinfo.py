"""
audioinfo.py

Copyright (C) 2008 concentricpuddle

This audio is part of puddletag, a semi-good music tag editor.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import mutagen, pdb
from os import path
from mutagen.id3 import APIC
import mutagen.oggvorbis, mutagen.flac, mutagen.apev2, mutagen.mp3


PATH = "__path"
FILENAME = "__filename"

TAGS = { "TIT1": "grouping",
        "TIT2": "title",
        "TIT3": "version",
        "TPE1": "artist",
        "TPE2": "performer", 
        "TPE3": "conductor",
        "TPE4": "arranger",
        "TEXT": "lyricist",
        "TCOM": "composer",
        "TENC": "encodedby",
        "TALB": "album",
        "TRCK": "track",
        "TPOS": "discnumber",
        "TSRC": "isrc",
        "TCOP": "copyright",
        "TPUB": "organization",
        "TSST": "part",
        "TOLY": "author",
        "TMOO": "mood",
        "TBPM": "bpm",
        "TDOR": "originaldate",
        "TOAL": "originalalbum",
        "TOPE": "originalartist",
        "WOAR": "website",
        "TXXX": "user",
        "TRSN" : "radiostationname",
        "TMED" : "mediatype",
        "TSOT" : "titlesortorder",
        "TOFN" : "originalfilename",
        "TSSE" : "encodingsettings",
        "TIPL" : "peopleinvolved",
        "TDRL" : "releasetime",
        "TRSO" : "radioowener",
        "TKEY" : "initialkey",
        "TSOA" : "albumsortorder",
        "TPRO" : "producednotice",
        "TDTG" : "taggingtime",
        "TDEN" : "encodingtime",
        "TSOP" : "performersortorder",
        "TCON" : "genre",
        "TOWN" : "fileowner",
        "TDLY" : "playlistdelay",
        "TLEN" : "length",
        "TFLT" : "filetype",
        "TMCL" : "musiciancredits",
        "TLAN" : "language",
        "TDAT" : "date",
        "COMM" : "comment",
        "TDRC" : "year",
        "TYER" : "year"
            
            
            # "language" should not make to TLAN. TLAN requires
            # an ISO language code, and QL tags are freeform.
            }
REVTAGS = {"encodingsettings" : "TSSE",
            "producednotice" : "TPRO",
            "performer" : "TPE2",
            "titlesortorder" : "TSOT",
            "radiostationname" : "TRSN",
            "filetype" : "TFLT",
            "lyricist" : "TEXT",
            "performersortorder" : "TSOP",
            "composer" : "TCOM",
            "encodedby" : "TENC",
            "discnumber" : "TPOS",
            "releasetime" : "TDRL",
            "album" : "TALB",
            "genre" : "TCON",
            "mood" : "TMOO",
            "copyright" : "TCOP",
            "author" : "TOLY",
            "length" : "TLEN",
            "encodingtime" : "TDEN",
            "version" : "TIT3",
            "originalalbum" : "TOAL",
            "website" : "WOAR",
            "conductor" : "TPE3",
            "radioowener" : "TRSO",
            "playlistdelay" : "TDLY",
            "initialkey" : "TKEY",
            "mediatype" : "TMED",
            "albumsortorder" : "TSOA",
            "part" : "TSST",
            "track" : "TRCK",
            "user" : "TXXX",
            "isrc" : "TSRC",
            "peopleinvolved" : "TIPL",
            "musiciancredits" : "TMCL",
            "taggingtime" : "TDTG",
            "originalfilename" : "TOFN",
            "originaldate" : "TDOR",
            "originalartist" : "TOPE",
            "language" : "TLAN",
            "artist" : "TPE1",
            "title" : "TIT2",
            "bpm" : "TBPM",
            "arranger" : "TPE4",
            "organization" : "TPUB",
            "fileowner" : "TOWN",
            "grouping" : "TIT1",
            "date" : "TDAT",
            "comment" : "COMM",
            "year" : "TDRC",
            "year" : "TYER"
            }

class Tag:
    """Class that operates on audio audio tags.
    Currently supports ogg and mp3 files.
    
    It can be used in two ways.
    
    >>>tag = audioinfo.Tag(filename)
    Gets the tags in the audio, filename
    as a dictionary in format {tag: value} in Tag.tags.
    
    On the other hand, if you have already created
    a tag object. Use link like so:
    
    >>>tag = audioinfo.Tag()
    >>>tag.link(filename)
    {'artist': "Artist", "track":"12", title:"Title", '__length':"5:14"}
    The tags are stored in tag.tags.
    
    File info tags like length start with '__'. 
    Usually, these tags are readonly.
    
    Use self.writetags to save tags."""
    
    #Stores the tag info in the format {tag:tag value}
    tags={}
    
    #The filename of the linked audio
    filename = None
    #The type of audio
    filetype=None
    (oggtype, flactype, apev2type, mp3type) = [mutagen.oggvorbis.OggVorbis, mutagen.flac.FLAC, mutagen.apev2.APEv2, mutagen.mp3.MP3]
    VORBISCOMMENT = [oggtype, flactype, apev2type]
    
    def __getitem__(self,key):
        """Get the tag value from self.tags"""
        try:
            return self.tags[key]
        except KeyError:
            pass
            
    def __init__(self,filename=None):
        """Links the audio"""
        if filename is not None:
            self.link(filename)
            
    def link(self, filename):
        """Links the audio, filename
        returns and sets self.tags if successful."""
            
        #Get the type of audio and set
        #self.filetype to it.
        self.filetype = None
        self.tags = {}
        audio = path.realpath(filename)
        try:
            audio = mutagen.File(filename)
        except (IOError, ValueError):
            return
        except:
            print filename
            return
        if audio is None:
            return
        if type(audio) == self.mp3type:
            for tagval in audio:
                if tagval in TAGS:
                    try:
                        self.tags[TAGS[tagval]] = audio[tagval].text[0]
                    except IndexError:
                        #The tag is empty, but it exists. Don't do anything.
                        pass
		                  
            #The year tag is not returned as text. Make it so.
            if 'year' in self.tags:
                self.tags["year"] = unicode(self.tags['year'])
            #Get the image data.
            try:
                x = [z for z in audio if z.startswith(u"APIC:")][0]
                self.tags["__image"] = [audio[x].data,audio[x].mime, audio[x].type]
            except IndexError:
                self.tags['__image'] = None
            
            try:
                x = [z for z in audio if z.startswith(u"COMM:")][-1]
                self.tags['comment'] = audio[x].text[0]
            except IndexError:
                pass
            
            try:
                x = [z for z in audio if z.startswith(u"TXXX:")][-1]
                if audio[x].desc not in self.tags:
                    self.tags[audio[x].desc] = audio[x].text[0]
            except IndexError:
                pass
            
        elif type(audio) in self.VORBISCOMMENT:
            for z in audio:
                self.tags[z.lower()] = audio.tags[z][0]
            if 'tracknumber' in self.tags:
                self.tags["track"] = self.tags["tracknumber"]
                del(self.tags["tracknumber"])
        else:
            #for z in audio.tags:
                #self.tags[z.lower()] = audio.tags[z][0]
            return
        
        self.filetype = type(audio)
        info = audio.info
        self.filename = path.realpath(filename)
        if self.filetype != self.flactype:
            self.tags.update({FILENAME: filename,
                                PATH: path.basename(filename),
                                "__folder": path.dirname(filename),
                                "__ext": path.splitext(filename)[1][1:],
                                "__bitrate": unicode(info.bitrate/1000) + u" kb/s",
                                "__frequency": unicode(info.sample_rate / 1000.0)[:4] + u" kHz"})
        else:
            self.tags.update({FILENAME: filename,
                                PATH: path.basename(filename),
                                "__folder": path.dirname(filename),
                                "__ext": path.splitext(filename)[1][1:],
                                "__bitrate": u"0" + u" kb/s",
                                "__frequency": unicode(info.sample_rate / 1000.0)[:4] + u" kHz"})
                                                                    
        seconds = long(info.length % 60)
        if seconds < 10:
            seconds = u"0" + unicode(seconds)
        self.tags["__length"] = "".join([unicode(long(info.length/60)),  ":", unicode(seconds)])
        return self.tags
                                
    def __setitem__(self,key,value):
        "See __getitem__"
        self.tags[key] = value
            
    def writetags(self, filename = None):
        """Writes the tags in self.tags
        to self.filename if no filename is specified."""
        
        if filename is None:
            filename = self.filename
        audio = mutagen.File(unicode(filename))
        if type(audio) == mutagen.mp3.MP3:
            newtag = []
            for tag, value in self.tags.items():
                try:
                    if not tag.startswith("__") and unicode(value):
                            audio[REVTAGS[tag]] = getattr(mutagen.id3, REVTAGS[tag])(encoding = 3, text = unicode(value))
                            newtag.append(REVTAGS[tag])
                except (KeyError, AttributeError):
                    audio[u'TXXX:' + unicode(tag)] = mutagen.id3.TXXX(1, tag, unicode(value))
                    newtag.append(u'TXXX:' + unicode(tag))
            
            toremove = [z for z in audio if z not in newtag]
            for z in toremove:
                del(audio[z])
            audio.save()
            
        elif self.filetype in self.VORBISCOMMENT:
            newtag = {}
            for tag, value in self.tags.items():
                try:
                    if not tag.startswith("__") and unicode(value):
                        newtag[tag] = value
                except AttributeError:
                        pass
            if "track" in newtag:
                newtag["tracknumber"] = newtag["track"]
                del newtag["track"]
            toremove = [z for z in audio if z not in newtag]
            for z in toremove:
                del(audio[z])
            audio.tags.update(newtag)
            audio.save()

