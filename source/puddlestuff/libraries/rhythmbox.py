from xml.dom import minidom
import pdb
from os import path
import sys
import urllib, os
try:
    import puddlestuff.audioinfo as audioinfo
except:
    sys.path.insert(1, '..')
    import audioinfo
FILENAME, PATH = audioinfo.FILENAME, audioinfo.PATH
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
from PyQt4.QtCore import *
from PyQt4.QtGui import *
try:
    import puddlestuff.musiclib as musiclib
except:
    import musiclib

name = "Rhythmbox"
description = "Rhythmbox Database"
author = 'concentricpuddle'

def getFilename(filename):
    filename = urllib.url2pathname(filename)
    try:
        filename = filename.encode('latin1').decode('utf8')
    except UnicodeDecodeError:
        print u"UnicodeDecodeError on: ", filename
        pass

    if filename.startswith(u'file://'):
        filename = filename[len(u'file://'):]
        return {u'__folder': path.dirname(filename),
                FILENAME: filename,
                PATH: path.basename(filename),
                u"__folder": path.dirname(filename),
                u"__ext": path.splitext(filename)[1][1:]}

getTime = lambda date: audioinfo.strtime(int(date))
getCreated = lambda created: {u'__created': getTime(created)}
getModified = lambda modified: {u'__modified': getTime(modified)}
getLength = lambda length: {u'__length': audioinfo.strlength(int(length))}
getBitRate = lambda bitrate: {u'__bitrate': bitrate + u' kb/s'}


CONVERSION = {u'title': u'title',
u'genre': u'genre',
u'artist': u'artist',
u'album': u'album',
u'track-number': u'track',
u'duration': getLength,
u'file-size': u'__size',
u'location': getFilename,
u'first-seen': getCreated,
u'last-seen': getModified,
u'bitrate': getBitRate,
u'disc-number': u'discnumber'}

setLength = lambda length: {'duration': unicode(audioinfo.lnglength(length))}
setCreated = lambda created: {'first-seen': unicode(audioinfo.lngtime(created))}
setBitrate = lambda bitrate: {'bitrate': unicode(audioinfo.lngfrequency(bitrate) / 1000)}
setModified = lambda modified: {'last-seen': unicode(audioinfo.lngtime(modified))}
setFilename = lambda filename: {u'location': u'file://' + unicode(QUrl.toPercentEncoding(filename, '/()"\'')).encode('utf8')}

RECONVERSION = {
    'title': 'title',
    'artist': 'artist',
    'album': 'album',
    'track': 'track-number',
    'discnumber': 'disc-number',
    'genre': 'genre',
    '__length': setLength,
    '__created': setCreated,
    '__bitrate': setBitrate,
    '__modified': setModified,
    '__filename': setFilename,
    '__size': 'file-size'}


class RhythmDB(ContentHandler):
    head = """<?xml version="1.0" standalone="yes"?>
<rhythmdb version="1.3">"""
    indent = " " * 4

    def __init__ (self, filename):
        self.tagval = ""
        self.name = ""
        self.stargetting = False
        self.values = {}
        self.current = "nothing"
        self.tracks = []
        self.albums = {}
        self.extravalues = []
        self.extras = False
        self.extratype = ""
        parser = make_parser()
        parser.setContentHandler(self)
        try:
            parser.parse(filename)
        except ValueError, detail:
            if not os.path.exists(filename):
                msg = "%s does not exist." % filename
            else:
                msg = "%s is not a valid Rhythmbox XML database." % filename
            raise musiclib.MusicLibError(0, msg)
        self.filename = filename

    def startElement(self, name, attrs):
        if name == 'entry':
            if attrs.get('type') == 'song':
                self.stargetting = True
            else:
                self.extratype = attrs.get('type')
                self.extras = True
                self.stargetting = True
        if self.stargetting and name != 'entry':
            self.current = name
            self.values[name] = ""

    def characters (self, ch):
        try:
            self.values[self.current] += ch
        except KeyError:
            self.values[self.current] = ch

    def endElement(self, name):
        if name == "entry" and self.stargetting:
            self.stargetting = False
            if not self.extras:
                audio = {}
                for tag, value in self.values.items():
                    try:
                        audio.update(CONVERSION[tag](value.strip()))
                    except TypeError:
                        audio[CONVERSION[tag]] = value.strip()
                    except KeyError:
                        audio["___" + tag] = value.strip()
                audio['__library'] = 'rhythmbox'

                if audio['artist'] not in self.albums:
                    self.albums[audio['artist']] = {}
                albums = self.albums[audio['artist']]
                if audio['album'] not in albums:
                    albums[audio['album']] = len(self.tracks)
                    self.tracks.append([audio])
                else:
                    index = albums[audio['album']]
                    self.tracks[index].append(audio)
            else:
                x = dict([(z, v.strip()) for z,v in self.values.items()])
                x['name'] = self.extratype
                self.extratype = ""
                self.extravalues.append(x)
                self.extras = False
            self.values = {}

    def getArtists(self):
        return self.albums.keys()

    def getAlbums(self, artist):
        try:
            return self.albums[artist].keys()
        except KeyError:
            return None

    def getTracks(self, artist, albums = None):
        ret = []
        if albums is None:
            albums = self.albums[artist].keys()

        if artist in self.albums:
            stored = self.albums[artist]
            for album in albums:
                if album in stored:
                    ret.extend(self.tracks[stored[album]])
        return [musiclib.Tag(self, z) for z in ret]

    def _escapedText(self, txt):
        result = txt
        result = result.replace("&", "&amp;")
        result = result.replace("<", "&lt;")
        result = result.replace(">", "&gt;")
        return result

    def delTracks(self, tracks):
        for track in tracks:
            track = audioinfo.stringtags(track)
            artist = track['artist']
            album = track['album']
            dbtracks = self.tracks[self.albums[artist][album]]
            dbtracks.remove(track)
            if not dbtracks:
                del(self.albums[artist][album])
            if not self.albums[artist]:
                del(self.albums[artist])

    def saveTracks(self, tracks):
        for old, new in tracks:
            old, new = audioinfo.stringtags(old), audioinfo.stringtags(new)
            artist = new['artist']
            album = new['album']
            if old['artist'] != artist:
                if artist in self.albums:
                    if album in self.albums[artist]:
                        index = self.albums[artist][album]
                        self.tracks[index].append(new)
                    else:
                        self.albums[artist][album] = len(self.tracks)
                        self.tracks.append([new])
                else:
                    self.albums[artist] = {album: len(self.tracks)}
                    self.tracks.append([new])
            elif album != old['album']:
                if album in self.albums[artist]:
                    self.albums[artist][album].append(new)
                else:
                    self.albums[artist][album] = len(self.tracks)
                    self.tracks.append([new])
            else:
                self.tracks[self.albums[artist][album]].append(new)
            self.delTracks([old])

    def save(self):
        filename = path.join(path.dirname(self.filename), 'rhythmbox.xml')
        f = open(filename, 'w')
        entry = [self.head + "\n"]
        for album in self.tracks:
            for track in album:
                entry.append(u'  <entry type="song">\n')
                for key, tagvalue in track.items():
                    try:
                        if key.startswith('___'):
                            tagname = key[len('___'):]
                        else:
                            temp = RECONVERSION[key](tagvalue)
                            tagname = temp.keys()[0]
                            tagvalue = temp[tagname]
                    except TypeError:
                        tagname = RECONVERSION[key]
                    except KeyError:
                        continue
                    entry.append(u'    <%s>%s</%s>\n' % (self._escapedText(tagname), self._escapedText(tagvalue), self._escapedText(tagname)))
                entry.append(u'  </entry>\n')
                f.write((u"".join(entry)).encode('utf-8'))
                entry = []

        entry = []
        for value in self.extravalues:
            entry.append('  <entry type ="%s">\n' % value['name'])
            [entry.append('    <%s>%s</%s>\n' %
                    (self._escapedText(val), self._escapedText(value[val]),
                    self._escapedText(val))) for val in value]
            entry.append("  </entry>\n")
            f.write((u"".join(entry)).encode('utf-8'))
            entry = []
        f.write("</rhythmdb>")
        f.close()
        backup = path.join(path.dirname(self.filename), 'oldrhythmdb.xml')
        if not path.exists(backup):
            os.rename(self.filename, backup)
        os.rename(filename, self.filename)

    def close(self):
        pass

    def search(self, term):
        term = term.upper()
        ret = []
        artists = set([z for z in self.albums if term in z.upper()])
        [ret.extend(self.getTracks(z)) for z in artists]
        others = set(self.albums).difference(artists)

        for artist in others:
            albums = self.albums[artist]
            for album in albums:
                if term in album.upper():
                    ret.extend(self.getTracks(artist, [album]))
                else:
                    index = self.albums[artist][album]
                    tracks = self.tracks[index]
                    for track in tracks:
                        for value in track.values():
                            if term in value.upper():
                                ret.append(track)
                                break
        return [musiclib.Tag(self, z) for z in ret]

    def updateSearch(self, term, tracks):
        tags = ['artist', 'title', FILENAME, '__path', 'album', 'genre',
                'comment', 'year']
        term = term.lower()
        tracks = []
        for audio in files:
            temp = audioinfo.stringtags(audio)
            for tag in tags:
                if term in temp[tag].lower():
                    tracks.append(audio)
                    break
        return tracks


class ConfigWindow(QWidget):
    def __init__(self, parent = None):
        QWidget.__init__(self, parent)
        self.dbpath = QLineEdit(path.join(unicode(QDir.homePath()), u".gnome2/rhythmbox/rhythmdb.xml"))

        vbox = QVBoxLayout()
        [vbox.addWidget(z) for z in [QLabel('&Database path'), self.dbpath]]

        hbox = QHBoxLayout()
        openfile = QPushButton("&Browse...")
        hbox.addStretch()
        hbox.addWidget(openfile)
        vbox.addLayout(hbox)
        self.connect(openfile, SIGNAL('clicked()'), self.getFile)
        vbox.addStretch()
        self.setLayout(vbox)
        self.dbpath.selectAll()
        self.dbpath.setFocus()

    def getFile(self):
        filedlg = QFileDialog()
        filename = unicode(filedlg.getOpenFileName(self,
            'Select RhythmBox database file.', self.dbpath.text()))
        if filename:
            self.dbpath.setText(filename)


    def getLibClass(self):
        return RhythmDB(unicode(self.dbpath.text()))

    def saveSettings(self):
        QSettings().setValue('Library/dbpath', QVariant(self.dbpath.text()))

def loadLibrary():
    settings = QSettings()
    return RhythmDB(unicode(settings.value('Library/dbpath').toString()))


