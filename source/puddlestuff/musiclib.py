from PyQt4.QtCore import *
from PyQt4.QtGui import *
from os import path
import sys, pdb
from puddlestuff.puddleobjects import PuddleDock, OKCancel, ProgressWin, PuddleThread, winsettings
import puddlestuff.audioinfo as audioinfo
(stringtags, FILENAME, READONLY, INFOTAGS) = (audioinfo.stringtags, audioinfo.FILENAME, audioinfo.READONLY, audioinfo.INFOTAGS)
import imp
from itertools import izip
from puddlestuff.constants import RIGHTDOCK
from collections import defaultdict
import puddlestuff.libraries as libraries
from functools import partial

class MusicLibError(Exception):
    def __init__(self, number, stringvalue):
        self.strerror = stringvalue
        self.number = number

errors = {
    0: "Library load error",
    1: "Library save error",
    2: "Library file load error",
    3: "Library file save error"}

class LibChooseDialog(QDialog):
    def __init__(self, parent = None):
        QDialog.__init__(self, parent)
        self.listbox = QListWidget()
        self.setWindowTitle('Import Music Library')
        winsettings('importmusiclib', self)

        self.libattrs = []
        for libname in libraries.__all__:
            try:
                lib =  __import__('puddlestuff.libraries.%s' % libname,
                                    fromlist=['puddlestuff', 'libraries'])
                if not hasattr(lib, 'InitWidget'):
                    raise Exception(u'Invalid library')
            except Exception, detail:
                sys.stderr.write(u'Error loading %s: %s\n' % (libname, unicode(detail)))
                continue
            try: name = lib.name
            except AttributeError: name = 'Anonymous Database'

            try: desc = lib.description
            except AttributeError: desc = 'Description was left out.'

            try: author = lib.author
            except AttributeError: author = 'Anonymous author.'

            self.libattrs.append({'name': name, 'desc':desc, 'author': author, 'module': lib})

        self.listbox.addItems([z['name'] for z in self.libattrs])
        self.stackwidgets = [z['module'].InitWidget() for z in  self.libattrs]
        self.connect(self.listbox, SIGNAL('currentRowChanged (int)'), self.loadLibConfig)

        okcancel = OKCancel()
        self.connect(okcancel, SIGNAL('ok'), self.loadLib)
        self.connect(okcancel, SIGNAL('cancel'), self.close)

        self.stack = QStackedWidget()
        self.stack.setFrameStyle(QFrame.Box)
        [self.stack.addWidget(z) for z in self.stackwidgets]

        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox,0)
        hbox.addWidget(self.stack,1)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addLayout(okcancel)

        self.setLayout(vbox)

    def loadLibConfig(self, number):
        if number > -1:
            self.stack.setCurrentWidget(self.stackwidgets[number])
            self.currentlib = self.libattrs[number]

    def _load_lib(self):
        try:
             return self.stack.currentWidget().library()
        except MusicLibError, details:
            return unicode(details.strerror)

    def loadLib(self):
        p = ProgressWin(self, 0, showcancel = False)
        p.show()
        t = PuddleThread(self._load_lib)
        t.start()
        while t.isRunning():
            QApplication.processEvents()
        library = t.retval
        p.close()
        QApplication.processEvents()
        if isinstance(library, basestring):
            QMessageBox.critical(self, u"Error", u'I encountered an error while loading the %s library: <b>%s</b>' \
                            % (unicode(self.currentlib['name']), library),
                            QMessageBox.Ok, QMessageBox.NoButton, QMessageBox.NoButton)
        else:
            dialog = partial(LibraryDialog, library)
            self.emit(SIGNAL('adddock'), 'Music Library', dialog, RIGHTDOCK)
            self.close()

class LibraryDialog(QWidget):
    def __init__(self, library=None, parent=None, status = None):
        QWidget.__init__(self, parent)
        self._library = library
        self.emits = ['loadtags']
        self.tree = LibraryTree(library)
        emit = lambda signal: lambda *args: self.emit(SIGNAL(signal), *args)
        self.connect(self.tree, SIGNAL('loadtags'), emit('loadtags'))
        vbox = QVBoxLayout()
        vbox.setMargin(0)
        hbox = QHBoxLayout()


        searchlabel = QLabel('&Search')
        self.searchtext = QLineEdit()
        searchbutton = QPushButton('&Go')
        self.connect(self.searchtext, SIGNAL('returnPressed()'),
                self.searchTree)
        self.connect(searchbutton, SIGNAL('clicked()'),
                self.searchTree)
        searchlabel.setBuddy(self.searchtext)
        searchbox = QHBoxLayout()
        searchbox.addWidget(searchlabel)
        searchbox.addWidget(self.searchtext)
        searchbox.addWidget(searchbutton)

        vbox.addLayout(hbox)
        vbox.addLayout(searchbox)
        vbox.addWidget(self.tree)
        self.setLayout(vbox)

        self.load_lib = self.tree.load_lib

        self.emits = ['loadtags']
        self.receives = [('deletedfromlib', self.tree.update_deleted),
                         ('libfilesedited', self.tree.update_edited)]

    def searchTree(self):
        self.tree.search(unicode(self.searchtext.text()))

    def saveSettings(self):
        p = ProgressWin(self, 0, showcancel = False)
        p.setWindowTitle('Saving music library...')
        p.show()
        t = PuddleThread(self._library.save)
        t.start()
        while t.isRunning():
            QApplication.processEvents()
        p.close()


class LibraryTree(QTreeWidget):
    def __init__(self, library, parent = None):
        QTreeWidget.__init__(self, parent)
        self.library = library
        self.setHeaderLabels(["Library Artists"])
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.AscendingOrder)
        self.load_lib(library)
        self._searchtracks = []
        self.connect(self, SIGNAL('itemCollapsed (QTreeWidgetItem *)'), self.setClosedIcon)
        self.connect(self, SIGNAL('itemExpanded (QTreeWidgetItem *)'), self.setOpenIcon)

    def load_lib(self, library):
        if self.library:
            self.library.close()
        self.fill_from_lib(library)
        self.library = library
        self.connect(self, SIGNAL('itemSelectionChanged()'), self.get_tracks)

    def fill_from_lib(self, library, artists = None):
        select = artists
        if not artists:
            self.clear()
            artists = library.artists
        albumslist = (library.get_albums(artist) for artist in artists)
        self.populate(izip(artists, albumslist), select)

    def populate(self, data, select = False):
        icon = self.style().standardIcon(QStyle.SP_DirClosedIcon)
        for artist, albums in data:
            if albums:
                top = QTreeWidgetItem([artist])
                top.setIcon(0, icon)
                self.addTopLevelItem(top)
                [top.addChild(QTreeWidgetItem([z])) for z in albums]
                if select:
                    top.setSelected(True)
                    self.expandItem(top)

    def setClosedIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirClosedIcon))

    def setOpenIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirOpenIcon))

    def get_tracks(self):
        if self._searchtracks:
            def artist_tracks(artist):
                tracks = []
                [tracks.extend(z) for z in self._searchtracks[artist].values()]
                return tracks
            album_tracks = lambda artist, album: self._searchtracks[artist][album]
        else:
            _libget = self.library.get_tracks
            album_tracks = lambda artist, album: _libget('artist',
                                artist, 'album', album)
            artist_tracks = lambda artist: _libget('artist', artist)

        total = []
        selected = self.selectedItems()
        toplevels = [z for z in selected if not z.parent()]
        self.blockSignals(True)
        for parent in toplevels:
            child = parent.child
            [child(row).setSelected(False) for row in
                range(parent.childCount())]
        self.blockSignals(False)
        selected = self.selectedItems()
        for item in self.selectedItems():
            tracks = []
            if item.parent() and item.parent() not in selected:
                album = unicode(item.text(0))
                artist = unicode(item.parent().text(0))
                tracks = album_tracks(artist, album)
            else:
                artist = unicode(item.text(0))
                tracks = artist_tracks(artist)
            total.extend(tracks)
        self.emit(SIGNAL('loadtags'), total)

    def update_deleted(self, tracks=None, artists = None):
        if self._searchtracks:
            return
        if tracks:
            data = set([track['artist'][0] for track in tracks])
        else:
            data = set(artists)

        lib_artists = self.library.artists
        get_albums = self.library.get_albums
        index = self.indexOfTopLevelItem
        take_item = self.takeTopLevelItem

        for artist in data:
            artist_item = self.findItems(artist, Qt.MatchExactly)[0]
            if artist in lib_artists:
                albums = get_albums(artist)
                get_child = artist_item.child
                remove = artist_item.removeChild

                children = (get_child(i) for i in
                                xrange(artist_item.childCount()))
                toremove = [child for child in children if
                                unicode(child.text(0)) not in albums]
                [remove(child) for child in toremove]
            else:
                take_item(index(artist_item))

    def update_edited(self, data):
        if self._searchtracks:
            return
        self.blockSignals(True)
        artists = [tag['artist'][0] if 'artist' in tag else artist
                    for artist, tag in data]
        self.update_deleted(artists = [z[0] for z in data])
        lib_artists = self.library.artists
        get_albums = self.library.get_albums
        index = self.indexOfTopLevelItem
        take_item = self.takeTopLevelItem

        newartists = []
        for artist in set(artists):
            artist_item = self.findItems(artist, Qt.MatchExactly)
            if artist_item:
                artist_item = artist_item[0]
                albums = get_albums(artist)
                get_child = artist_item.child
                add = artist_item.addChild

                tree_albums = [unicode(get_child(i).text(0)) for i in
                                xrange(artist_item.childCount())]
                items = [QTreeWidgetItem([album]) for album in albums if album not
                    in tree_albums]
                def select(item):
                    add(item)
                    item.setSelected(True)
                map(select, items)
                self.expandItem(artist_item)
            else:
                newartists.append(artist)
        if newartists:
            self.fill_from_lib(self.library, newartists)
        self.blockSignals(False)

    def search(self, text):
        if not text:
            self._searchtracks = []
            self.fill_from_lib(self.library)
            return
        self.blockSignals(True)
        self.clear()
        tracks = self.library.search(text)
        grouped = defaultdict(lambda: defaultdict(lambda: []))
        artist_tag = 'artist'
        album_tag = 'album'
        def add(track):
            artist = track[artist_tag][0] if artist_tag in track else ''
            album = track[album_tag][0] if album_tag in track else ''
            grouped[artist][album].append(track)
        [add(track) for track in tracks]
        self.populate(grouped.items())
        self._searchtracks = grouped
        self.blockSignals(False)

obj = QObject()
obj.emits = ['adddock']
obj.receives = []
name = 'Music Library'

control = ('Music Library', LibraryDialog, RIGHTDOCK, False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    #qb = LibraryTree(quodlibetlib.QuodLibet('songs'))
    qb = LibChooseDialog()
    qb.show()
    app.exec_()