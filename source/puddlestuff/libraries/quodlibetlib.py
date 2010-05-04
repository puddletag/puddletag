# -*- coding: utf8 -*-
import sys, os, unittest, time, pdb, shutil
from os import path
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import cPickle as pickle
from puddlestuff.audioinfo.util import (FILENAME, DIRPATH, PATH, EXTENSION, READONLY,
                            FILETAGS, INFOTAGS, stringtags, getinfo, strlength,
                            MockTag, isempty, lngtime, lngfrequency,
                            lnglength, setdeco, getdeco)
import puddlestuff.audioinfo as audioinfo
from puddlestuff.musiclib import MusicLibError
ATTRIBUTES = ('bitrate', 'length', 'modified')
import quodlibet.config
from quodlibet.parse import Query
from functools import partial
from puddlestuff.constants import HOMEDIR
from collections import defaultdict
from puddlestuff.util import to_string

def strbitrate(bitrate):
    """Returns a string representation of bitrate in kb/s."""
    return unicode(bitrate/1000) + u' kb/s'

def strtime(seconds):
    """Converts UNIX time(in seconds) to more Human Readable format."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))


timetags = ['~#added', '~#lastplayed', '~#laststarted']
timefunc = lambda key: lambda value : {'__%s' % key[2:]: strtime(value)}
mapping = dict([(key, timefunc(key)) for key in timetags])

mapping.update({'tracknumber': lambda value: {'track': [value]},
                '~#bitrate' : lambda value: {'__bitrate': strbitrate(value)},
                '~#length': lambda value: {'__length': strlength(value)},
                '~#playcount': lambda value: {'_playcount': [unicode(value)]},
                '~#rating': lambda value: {'_rating': [unicode(value)]},
                '~#skipcount': lambda value: {'_skipcount': [unicode(value)]},
                '~mountpoint': lambda value: {'__mountpoint': value},
                '~#mtime': lambda value : {'__modified': strtime(value)},
                '~filename': lambda value : {'__path': value.decode('utf8')}})

timetags = ['__added', '__lastplayed', '__laststarted',]
timefunc = lambda key: lambda value : {'~#%s' % key[2:]: lngtime(value)}
revmapping = dict([(key, timefunc(key)) for key in timetags])
revmapping.update({'track': lambda value: {'tracknumber': value},
                '__bitrate' : lambda value: {'~#bitrate': lngfrequency(value)},
                '__length': lambda value: {'~#length': lnglength(value)},
                '_playcount': lambda value: {'~#playcount': long(value)},
                '_rating': lambda value: {'~#rating': float(value)},
                '_skipcount': lambda value: {'~#skipcount': long(value)},
                '__mountpoint': lambda value: {'~mountpoint': value},
                '__modified': lambda value : {'~#mtime': lngtime(value)},
                '__path': lambda value : {'~filename': value.encode('utf8')}})

class Tag(MockTag):
    """Use as base for all tag classes."""
    mapping = audioinfo.mapping['puddletag'] if 'puddletag' in audioinfo.mapping else {}
    revmapping = audioinfo.revmapping['puddletag'] if 'puddletag' in audioinfo.revmapping else {}
    IMAGETAGS = ()
    _hash = {PATH: 'filepath',
            FILENAME:'filename',
            EXTENSION: 'ext',
            DIRPATH: 'dirpath'}
    def __init__(self, libclass, libtags):
        MockTag.__init__(self)
        self.library = libclass
        self.remove = partial(libclass.delete, track=libtags)
        self._libtags = libtags
        tags = {}
        for key, value in libtags.items():
            if key in mapping:
                tags.update(mapping[key](value))
            else:
                tags[key] = [value]
        self._tags = tags
        self._set_attrs(ATTRIBUTES)
        self.filepath = tags[PATH]
        info = getinfo(self.filepath)
        self.size = info['__size']
        self._tags['__size'] = self.size
        self.accessed = info['__accessed']
        self._tags['__accessed'] = self.accessed

    def _getfilepath(self):
        return self._tags[PATH]

    def _setfilepath(self,  val):
        self._libtags['~filename'] = val.encode('utf8')
        self._tags.update({PATH: val,
                           DIRPATH: path.dirname(val),
                           FILENAME: path.basename(val),
                           EXTENSION: path.splitext(val)[1][1:]})

    filepath = property(_getfilepath, _setfilepath)

    @getdeco
    def __getitem__(self, key):
        if key in self._tags:
            return self._tags[key]
        return ['']

    @setdeco
    def __setitem__(self, key, value):
        if key in READONLY:
            return
        elif key in FILETAGS:
            setattr(self, self._hash[key], value)
            return

        if key not in INFOTAGS and isempty(value):
            del(self[key])
        elif key in INFOTAGS or isinstance(key, (int, long)):
            self._tags[key] = value
        elif (key not in INFOTAGS) and isinstance(value, (basestring, int, long)):
            self._tags[key] = [unicode(value)]
        else:
            self._tags[key] = [unicode(z) for z in value]

    def save(self, justrename = False):
        if justrename:
            return
        libtags = self._libtags
        tags = self._tags
        newartist = tags['artist'][0] if tags.get('artist') else u''
        oldartist = libtags['artist'] if libtags.get('artist') else u''

        newalbum = tags['album'][0] if tags.get('album') else u''
        oldalbum = libtags['album'] if libtags.get('album') else u''

        self._libtags.update(self._tolibformat())
        self._libtags.write()
        if (newartist != oldartist) or (newalbum != oldalbum):
            self.library.update(oldartist, oldalbum, libtags)

    def sget(self, key):
        return self[key] if self.get(key) else ''

    def _tolibformat(self):
        libtags = {}
        tags = stringtags(self._tags).items()
        for key, value in tags:
            if key in revmapping:
                libtags.update(revmapping[key](value))
            elif key in INFOTAGS:
                continue
            else:
                libtags[key] = value
        if '__accessed' in libtags:
            del(libtags['__accessed'])

        if '__size' in libtags:
            del(libtags['__size'])
        return libtags

class QuodLibet(object):
    def __init__(self, filepath, config = None):
        self._tracks = pickle.load(open(filepath, 'rb'))
        if not config:
            config = os.path.join(os.path.dirname(filepath), u'config')
        try:
            quodlibet.config.init(config)
        except ValueError:
            "Raised if this method's called twice."
        self._filepath = filepath
        cached = defaultdict(lambda: defaultdict(lambda: []))
        for track in self._tracks:
            if track.get('artist'):
                cached[track['artist']][track['album'] if 'album'
                    in track else ''].append(track)
            else:
                cached[''][track['album'] if 'album'
                    in track else ''].append(track)
        self._cached = cached

    def get_tracks(self, maintag, mainval, secondary=None, secvalue=None):
        if secondary and secvalue:
            if secondary == 'album' and maintag == 'artist':
                return map(lambda track : Tag(self, track),
                                self._cached[mainval][secvalue])
            def getvalue(track):
                if (track.get(maintag) == mainval) and (
                    track.get(secondary) == secvalue):
                    return Track(self, track)
        else:
            if maintag == 'artist':
                tracks = []
                [tracks.extend(z) for z in self._cached[mainval].values()]
                return map(lambda track: Tag(self, track), tracks)
            def getvalue(track):
                if track.get(maintag) == mainval:
                    return Tag(self, track)

        return filter(getvalue, self._tracks)

    def distinct_values(self, tag):
        return set([track[tag] if tag in track else '' for track in self._tracks])

    def distinct_children(self, tag, value, childtag):
        return set([track[childtag] if childtag in track else '' for track in
                    self._tracks if (tag in track) and (track[tag] == value)])

    def _artists(self):
        return self._cached.keys()

    artists = property(_artists)

    def get_albums(self, artist):
        return self._cached[artist].keys()

    def save(self):
        pickle.dump(self._tracks, open(self._filepath, 'wb'))

    def delete(self, track):
        artist = to_string(track['artist'])
        album = to_string(track['album'])
        self._cached[artist][album].remove(track)
        self._tracks.remove(track)

    def tree(self):
        title = 'title'
        for artist in self.artists:
            print artist
            albums = self.get_albums(artist)
            for album in albums:
                print u'  ', album
                tracks = self.get_tracks('artist', artist, 'album', album)
                for track in tracks:
                    print u'      ', track[title][0] if title in track else u''

    def close(self):
        pass

    def search(self, text):
        try:
            filt = Query(text).search
        except Query.error:
            return []
        else:
            return [Tag(self, track) for track in filter(filt, self._tracks)]

    def update(self, artist, album, track):
        cached = self._cached
        if not artist:
            artist = None
        if not album:
            album = None
        cached[artist][album].remove(track)
        if not cached[artist][album]:
            del(cached[artist][album])
        if not cached[artist]:
            del(cached[artist])
        trackartist = track['artist'] if track.get('artist') else u''
        trackalbum = track['album'] if track.get('album') else u''
        cached[trackartist][trackalbum].append(track)

class InitWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.dbpath = QLineEdit(os.path.join(HOMEDIR, u".quodlibet/songs"))
        self.configpath = QLineEdit(os.path.join(HOMEDIR, u".quodlibet/config"))

        vbox = QVBoxLayout()
        def label(text, control):
            l = QLabel(text)
            l.setBuddy(control)
            return l

        vbox.addWidget(label('&Library Path', self.dbpath))

        hbox = QHBoxLayout()
        select_db = QPushButton("...")
        self.connect(select_db, SIGNAL('clicked()'), self.select_db)
        hbox.addWidget(self.dbpath)
        hbox.addWidget(select_db)
        vbox.addLayout(hbox)

        vbox.addStretch()
        vbox.addWidget(label('&Config Path', self.configpath))

        hbox = QHBoxLayout()
        select_config = QPushButton("...")
        self.connect(select_config, SIGNAL('clicked()'), self.select_config)
        hbox.addWidget(self.configpath)
        hbox.addWidget(select_config)
        vbox.addLayout(hbox)

        vbox.addStretch(1)
        self.setLayout(vbox)
        self.dbpath.selectAll()
        self.configpath.selectAll()
        self.dbpath.setFocus()

    def select_db(self):
        filedlg = QFileDialog()
        filename = filedlg.getOpenFileName(self,
            'Select Quodlibet database file.', self.dbpath.text())
        if filename:
            self.dbpath.setText(filename)

    def select_config(self):
        filedlg = QFileDialog()
        filename = filedlg.getOpenFileName(self,
            'Select Quodlibet config file.', self.configpath.text())
        if filename:
            self.configpath.setText(filename)

    def library(self):
        dbpath = unicode(self.dbpath.text())
        configpath = unicode(self.configpath.text())
        try:
            return QuodLibet(dbpath, configpath)
        except (IOError, OSError), e:
            raise MusicLibError(0, u'%s (%s)' % (e.strerror, e.filename))
        except (pickle.UnpicklingError, EOFError):
            raise MusicLibError(0, u'%s is an invalid QuodLibet music library file.' % dbpath)

name = u'Quodlibet'

if __name__ == '__main__':
    #unittest.main()
    import time
    lib = QuodLibet('/home/keith/.quodlibet/songs')
    pdb.set_trace()
    t = time.time()
    i = 0
    while i < 200:
        lib.get_tracks('artist', 'Alicia Keys')#, secondary=None, secvalue=None):
        i += 1
    print time.time() - t

    #app = QApplication([])
    #win = ConfigWindow()
    #win.show()
    #app.exec_()
