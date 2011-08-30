# -*- coding: utf-8 -*-
import sys
    
import os, time, pdb, traceback
import cPickle as pickle

from collections import defaultdict
from functools import partial

from PyQt4.QtCore import *
from PyQt4.QtGui import *

import quodlibet.config
from quodlibet.parse import Query

import puddlestuff.audioinfo as audioinfo

from puddlestuff.audioinfo.tag_versions import tags_in_file
from puddlestuff.audioinfo.util import (del_deco, fn_hash, getdeco,
    isempty, keys_deco, lngfrequency, lnglength, lngtime, set_total, setdeco,
    stringtags, strlength, unicode_list, CaselessDict, MockTag)
from puddlestuff.constants import HOMEDIR
from puddlestuff.musiclib import MusicLibError
from puddlestuff.util import to_string, translate

model_tag = audioinfo.model_tag

ATTRIBUTES = ['length', 'accessed', 'size', 'created',
    'modified', 'filetype']

def strbitrate(bitrate):
    """Returns a string representation of bitrate in kb/s."""
    return unicode(bitrate/1000) + u' kb/s'

def strtime(seconds):
    """Converts UNIX time(in seconds) to more Human Readable format."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))


time_fields = ['~#added', '~#lastplayed', '~#laststarted']
timefunc = lambda key: lambda value : {'__%s' % key[2:]: strtime(value)}
mapping = dict([(key, timefunc(key)) for key in time_fields])

mapping.update({
    'tracknumber': lambda value: {'track': [value]},
    '~#bitrate' : lambda value: {'__bitrate': strbitrate(value)},
    '~#length': lambda value: {'__length': strlength(value)},
    '~#playcount': lambda value: {'playcount': [unicode(value)]},
    '~#rating': lambda value: {'rating': [unicode(value)]},
    '~#skipcount': lambda value: {'__skipcount': [unicode(value)]},
    '~mountpoint': lambda value: {'__mountpoint': value},
    '~#mtime': lambda value : {'__modified': strtime(value)},
    '~picture': lambda value: {'__picture': value},
    })

time_fields = ['__added', '__lastplayed', '__laststarted',]
timefunc = lambda key: lambda value : {'~#%s' % key[2:]: lngtime(value)}
revmapping = dict([(key, timefunc(key)) for key in time_fields])
revmapping.update({
    'track': lambda value: {'tracknumber': value},
    '__bitrate' : lambda value: {'~#bitrate': lngfrequency(value)},
    '__length': lambda value: {'~#length': lnglength(value)},
    'playcount': lambda value: {'~#playcount': int(value)},
    'rating': lambda value: {'~#rating': float(value)},
    '__skipcount': lambda value: {'~#skipcount': int(value)},
    '__mountpoint': lambda value: {'~mountpoint': value},
    '__modified': lambda value : {'~#mtime': lngtime(value)},
    '__picture': lambda value: {'~picture': to_string(value)},
    })

class Tag(MockTag):
    """Use as base for all tag classes."""
    mapping = audioinfo.mapping.get('puddletag', {})
    revmapping = audioinfo.revmapping.get('puddletag', {})
    IMAGETAGS = ()

    def __init__(self, libclass, libtags):
        MockTag.__init__(self)

        self.__tags = CaselessDict()
        tags = self.__tags

        tags.update(self.load(libtags['~filename'])[0])
        tags['__tag_read'] = u'QuodLibet'

        self.library = libclass
        self.remove = partial(libclass.delete, track=libtags)
        self._libtags = libtags

        for key, value in libtags.items():
            if not value and not isinstance(value, (int, long)):
                continue
            if key in mapping:
                tags.update(mapping[key](value))
            else:
                if not isinstance(value, unicode): #Strings
                    try: value = unicode(value, 'utf8', 'replace')
                    except (TypeError, ValueError):
                        try: value = unicode(value) #Usually numbers
                        except:
                            traceback.print_exc()
                            continue
                tags[key] = [value]
        del(tags['~filename'])

        self.filepath = libtags['~filename']
        self.set_attrs(ATTRIBUTES, self.__tags)
        self.update_tag_list()

    def get_filepath(self):
        return MockTag.get_filepath(self)

    def set_filepath(self,  val):
        self.__tags.update(MockTag.set_filepath(self, val))

    filepath = property(get_filepath, set_filepath)

    images = property(lambda s: [], lambda s: [])

    def __contains__(self, key):
        if self.revmapping:
            key = self.revmapping.get(key, key)
        return key in self.__tags

    def __deepcopy__(self, memo=None):
        tag = Tag(self._libclass, self._libtags)
        tag.update(deepcopy(self.__tags))
        return tag

    @del_deco
    def __delitem__(self, key):
        if key.startswith('__'):
            return
        else:
            if key == 'track':
                del(self._libtags['tracknumber'])
                del(self.__tags['track'])
            else:
                if key in self._libtags:
                    del(self._libtags[key])
                    del(self.__tags[key])

    @getdeco
    def __getitem__(self, key):
        return self.__tags[key]

    @setdeco
    def __setitem__(self, key, value):
        if key.startswith('__'):
            if key == '__total':
                set_total(self, value)
            elif key in fn_hash:
                setattr(self, fn_hash[key], value)
        elif isempty(value):
            if key in self:
                del(self[key])
            else:
                return
        else:
            self.__tags[key] = unicode_list(value)

    def delete(self):
        raise NotImplementedError

    @keys_deco
    def keys(self):
        return self.__tags.keys()

    def save(self, justrename = False):
        libtags = self._libtags
        tags = self.__tags
        newartist = to_string(tags.get('artist', [u'']))
        oldartist = libtags.get('artist', u'')

        newalbum = to_string(tags.get('album', [u'']))
        oldalbum = libtags.get('album', u'')

        self._libtags.update(self._tolibformat())
        self._libtags.write()
        if (newartist != oldartist) or (newalbum != oldalbum):
            self.library.update(oldartist, oldalbum, libtags)
        self.library.edited = True
        self.update_tag_list()

    def _tolibformat(self):
        libtags = {}
        tags = stringtags(self.__tags).items()
        for key, value in tags:
            if key in revmapping:
                libtags.update(revmapping[key](value))
            elif key.startswith('__'):
                continue
            else:
                libtags[key] = value

        libtags['~filename'] = self.filepath
        return libtags

    def update_tag_list(self):
        l = tags_in_file(self.filepath)
        if l:
            self.__tags['__tag'] = u'QuodLibet, ' + u', '.join(l)
        else:
            self.__tags['__tag'] = u'QuodLibet'

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
            cached[track.get('artist', u'')][track.get('album', u'')
                ].append(track)
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
        try:
            cached[artist][album].remove(track)
        except ValueError:
            pass
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
    lib = QuodLibet('/home/keith/.quodlibet/songs')
    artists = lib.artists
    import random
    d = defaultdict(lambda: defaultdict(lambda: []))
    for nothing in xrange(20):
        artist = artists[random.randint(0, len(artists))]
        for album, tracks in lib._cached[artist].items():
            d[artist][album] = [Tag(lib, t).usertags for t in tracks]
    import pprint
    f = {}
    for z in d:
        f[z] = dict(d[z])
    pprint.pprint(f)
        
            
        
