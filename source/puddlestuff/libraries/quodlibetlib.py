# -*- coding: utf-8 -*-
import sys, os, unittest, time, pdb, shutil
from os import path
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import cPickle as pickle
from puddlestuff.audioinfo.util import (FILENAME, DIRPATH, PATH, EXTENSION, READONLY,
    FILETAGS, INFOTAGS, stringtags, getinfo, strlength, MockTag, isempty, 
    lngtime, lngfrequency, lnglength, setdeco, getdeco, DIRNAME)
import puddlestuff.audioinfo as audioinfo
model_tag = audioinfo.model_tag
from puddlestuff.musiclib import MusicLibError
ATTRIBUTES = ['length', 'accessed', 'size', 'created',
    'modified', 'filetype']
import quodlibet.config
from quodlibet.parse import Query
from functools import partial
from puddlestuff.constants import HOMEDIR
from collections import defaultdict
from puddlestuff.util import to_string, translate
import shutil
from itertools import ifilter

def strbitrate(bitrate):
    """Returns a string representation of bitrate in kb/s."""
    return unicode(bitrate/1000) + u' kb/s'

def strtime(seconds):
    """Converts UNIX time(in seconds) to more Human Readable format."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))


timetags = ['~#added', '~#lastplayed', '~#laststarted']
timefunc = lambda key: lambda value : {'__%s' % key[2:]: strtime(value)}
mapping = dict([(key, timefunc(key)) for key in timetags])

mapping.update({
    'tracknumber': lambda value: {'track': [value]},
    '~#bitrate' : lambda value: {'__bitrate': strbitrate(value)},
    '~#length': lambda value: {'__length': strlength(value)},
    '~#playcount': lambda value: {'_playcount': [unicode(value)]},
    '~#rating': lambda value: {'_rating': [unicode(value)]},
    '~#skipcount': lambda value: {'_skipcount': [unicode(value)]},
    '~mountpoint': lambda value: {'__mountpoint': value},
    '~#mtime': lambda value : {'__modified': strtime(value)},
    '~picture': lambda value: {'__picture': value},
    })

timetags = ['__added', '__lastplayed', '__laststarted',]
timefunc = lambda key: lambda value : {'~#%s' % key[2:]: lngtime(value)}
revmapping = dict([(key, timefunc(key)) for key in timetags])
revmapping.update({
    'track': lambda value: {'tracknumber': value},
    '__bitrate' : lambda value: {'~#bitrate': lngfrequency(value)},
    '__length': lambda value: {'~#length': lnglength(value)},
    '_playcount': lambda value: {'~#playcount': int(value)},
    '_rating': lambda value: {'~#rating': float(value)},
    '_skipcount': lambda value: {'~#skipcount': int(value)},
    '__mountpoint': lambda value: {'~mountpoint': value},
    '__modified': lambda value : {'~#mtime': lngtime(value)},
    '__picture': lambda value: {'~picture': to_string(value)},
    })

class Tag(MockTag):
    """Use as base for all tag classes."""
    mapping = audioinfo.mapping.get('puddletag', {})
    revmapping = audioinfo.revmapping.get('puddletag', {})
    IMAGETAGS = ()
    _hash = {PATH: 'filepath',
            FILENAME:'filename',
            EXTENSION: 'ext',
            DIRPATH: 'dirpath',
            DIRNAME: 'dirname'}

    def __init__(self, libclass, libtags):
        MockTag.__init__(self)
        self.library = libclass
        self.remove = partial(libclass.delete, track=libtags)
        self._libtags = libtags
        tags = {}
        for key, value in libtags.items():
            if not value and not isinstance(value, (int, long)):
                continue
            if key in mapping:
                tags.update(mapping[key](value))
            else:
                if not isinstance(value, unicode):
                    try:
                        value = unicode(value, 'utf8')
                    except (TypeError, ValueError):
                        try:
                            value = unicode(value)
                        except:
                            traceback.print_exc()
                            continue
                tags[key] = [value]
        del(tags['~filename'])
        
        self._tags = tags
        self.filepath = libtags['~filename']
        self._tags.update(getinfo(self.filepath))
        self.set_attrs(ATTRIBUTES, self._tags)

    def get_filepath(self):
        return MockTag.get_filepath(self)

    def set_filepath(self,  val):
        self._tags.update(MockTag.set_filepath(self, val))

    filepath = property(get_filepath, set_filepath)

    def _get_images(self):
        return []

    def _set_images(self, images):
        return

    images = property(_get_images, _set_images)

    def __contains__(self, key):
        return key in self._tags

    def __delitem__(self, key):
        if key == '__image':
            return
        elif key.startswith('__'):
            return
        else:
            if key == 'track':
                del(self._libtags['tracknumber'])
                del(self._tags['track'])
            else:
                if key in self._libtags:
                    del(self._libtags[key])
                    del(self._tags[key])

    @getdeco
    def __getitem__(self, key):
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
        elif key in INFOTAGS or isinstance(key, (int, long)):
            self._tags[key] = value
        elif (key not in INFOTAGS) and isinstance(value, (basestring, int, long)):
            self._tags[key] = [unicode(value)]
        else:
            self._tags[key] = [unicode(z) for z in value]

    def delete(self):
        raise NotImplementedError

    def keys(self):
        return self._tags.keys()

    def save(self, justrename = False):
        libtags = self._libtags
        tags = self._tags
        newartist = tags.get('artist', [u''])
        oldartist = libtags.get('artist', u'')

        newalbum = tags.get('album', [u''])[0]
        oldalbum = libtags.get('album', u'')

        self._libtags.update(self._tolibformat())
        self._libtags.write()
        if (newartist != oldartist) or (newalbum != oldalbum):
            self.library.update(oldartist, oldalbum, libtags)
        self.library.edited = True

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
        libtags['~filename'] = self.filepath
        if '__accessed' in libtags:
            del(libtags['__accessed'])

        if '__size' in libtags:
            del(libtags['__size'])
        return libtags

Tag = audioinfo.model_tag(Tag)

class QuodLibet(object):
    def __init__(self, filepath):
        self.edited = False
        self._tracks = pickle.load(open(filepath, 'rb'))

        try:
            quodlibet.config.init()
        except ValueError:
            pass

        self._filepath = filepath
        cached = defaultdict(lambda: defaultdict(lambda: []))
        for track in self._tracks:
            if track.get('artist'):
                cached[track['artist']][track.get('album', u'')].append(track)
            else:
                cached[u''][track.get('album', u'')].append(track)
        self._cached = cached

    def get_tracks(self, maintag, mainval, secondary=None, secvalue=None):

        exists = lambda t: os.path.exists(t['~filename'])
        
        if secondary and secvalue:
            if secondary == 'album' and maintag == 'artist':
                tracks = (Tag(self, track) for track in
                    self._cached[mainval][secvalue] if exists(track))
                return filter(None, tracks)
            else:
                def getvalue(track):
                    if (track.get(maintag) == mainval) and (
                        track.get(secondary) == secvalue):
                        return Tag(self, track)
        else:
            if maintag == 'artist':
                tracks = []
                [tracks.extend(z) for z in self._cached[mainval].values()]
                return [Tag(self, track) for track in tracks if 
                    exists(track)]

            def getvalue(track):
                if track.get(maintag) == mainval:
                    return Tag(self, track)

        return filter(getvalue, self._tracks)

    def distinct_values(self, field):
        return set([track.get(field, u'') for track in self._tracks])

    def distinct_children(self, parent, value, child):
        return set([track.get(child, u'') for track in
            self._tracks if track.get(parent, u'') == value])
            
    def _artists(self):
        return self._cached.keys()

    artists = property(_artists)

    def get_albums(self, artist):
        return self._cached[artist].keys()

    def save(self):
        if not self.edited:
            return
        filepath = self._filepath + u'.puddletag'
        pickle.dump(self._tracks, open(filepath, 'wb'))
        os.rename(self._filepath, self._filepath +  u'.bak')
        os.rename(filepath, self._filepath)

    def delete(self, track):
        artist = to_string(track.get('artist', u''))
        album = to_string(track.get('album', u''))
        self._cached[artist][album].remove(track)
        self._tracks.remove(track)
        if not self._cached[artist][album]:
            del(self._cached[artist][album])
            if not self._cached[artist]:
                del(self._cached[artist])
        self.edited = True

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
        cached[artist][album].remove(track)
        if not cached[artist][album]:
            del(cached[artist][album])
        if not cached[artist]:
            del(cached[artist])
        trackartist = track.get('artist', u'')
        trackalbum = track.get('album', u'')
        cached[trackartist][trackalbum].append(track)

class DirModel(QDirModel):
    
    def data(self, index, role=Qt.DisplayRole):
        if (role == Qt.DisplayRole and index.column() == 0):
            path = QDir.toNativeSeparators(self.filePath(index))
            if path.endsWith(QDir.separator()):
                path.chop(1)
            return path
        return QDirModel.data(self, index, role)

class DirLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super(DirLineEdit, self).__init__(*args, **kwargs)
        completer = QCompleter()
        completer.setCompletionMode(QCompleter.PopupCompletion)
        dirfilter = QDir.AllEntries | QDir.NoDotAndDotDot | QDir.Hidden
        sortflags = QDir.DirsFirst | QDir.IgnoreCase
        
        dirmodel = QDirModel(['*'], dirfilter, sortflags, completer)
        completer.setModel(dirmodel)
        self.setCompleter(completer)
        

class InitWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.dbpath = DirLineEdit(os.path.join(HOMEDIR, u".quodlibet/songs"))
        self.configpath = DirLineEdit(os.path.join(HOMEDIR, u".quodlibet/config"))

        vbox = QVBoxLayout()
        def label(text, control):
            l = QLabel(text)
            l.setBuddy(control)
            return l

        vbox.addWidget(label(translate("QuodLibet", '&Library Path'), self.dbpath))

        hbox = QHBoxLayout()
        select_db = QPushButton(translate("QuodLibet", "..."))
        self.connect(select_db, SIGNAL('clicked()'), self.select_db)
        hbox.addWidget(self.dbpath)
        hbox.addWidget(select_db)
        vbox.addLayout(hbox)

        vbox.addStretch(1)
        self.setLayout(vbox)

    def select_db(self):
        filedlg = QFileDialog()
        filename = filedlg.getOpenFileName(self,
            translate("QuodLibet", 'Select QuodLibet library file...'),
            self.dbpath.text())
        if filename:
            self.dbpath.setText(filename)

    def library(self):
        dbpath = self.dbpath.text().toLocal8Bit()
        try:
            return QuodLibet(dbpath)
        except (IOError, OSError), e:
            raise MusicLibError(0, translate(
                "QuodLibet", '%1 (%2)').arg(e.strerror).arg(e.filename))
        except (pickle.UnpicklingError, EOFError):
            raise MusicLibError(0, translate("QuodLibet",
                '%1 is an invalid QuodLibet music library file.').arg(dbpath))

name = u'Quodlibet'

if __name__ == '__main__':
    #unittest.main()
    import time
    lib = QuodLibet('')
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
