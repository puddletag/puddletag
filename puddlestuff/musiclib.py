# -*- coding: utf-8 -*-
"""Module for importing music libraries into puddletag.

See puddlestuff.libraries.quodlibetlib for an example implementation.

Classes of interest:

LibraryWidget->Shows a tree view of library with search edit.
LibraryTree->Actual widget used to show library info.

"""
import sys
from collections import defaultdict
from functools import partial

from PyQt5.QtCore import QObject, Qt, pyqtRemoveInputHook, pyqtSignal
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QDialog, QFrame, QHBoxLayout, QLineEdit, \
    QListWidget, QMessageBox, QPushButton, QStackedWidget, QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, \
    QWidget

from . import libraries

from .constants import RIGHTDOCK
from .puddleobjects import (winsettings, OKCancel,
                            ProgressWin, PuddleThread)
from .util import to_string
from .translations import translate

pyqtRemoveInputHook()

errors = {
    0: "Library load error",
    1: "Library save error",
    2: "Library file load error",
    3: "Library file save error"}

extralibs = []


def select_add_child(item, child):
    item.addChild(child)
    item.setSelected(True)


class MusicLibError(Exception):
    def __init__(self, number, stringvalue):
        Exception.__init__(self)
        self.strerror = stringvalue
        self.number = number


class TreeWidgetItem(QTreeWidgetItem):
    def __lt__(self, item):
        if self.text(0).upper() < item.text(0).upper():
            return True
        return False


class ParentItem(TreeWidgetItem):
    def __init__(self, artist, albums=None, parent=None):
        self.artist = artist

        TreeWidgetItem.__init__(self, parent, [artist])

        if albums:
            children = [ChildItem(album, artist, self) for album in albums]
            self.addChildren(children)

    @property
    def albums(self):
        return [ch.album for ch in self.children]

    @property
    def children(self):
        count = self.childCount()
        if count <= 0:
            return []
        return [self.child(i) for i in range(count)]

    def addChild(self, ch):
        TreeWidgetItem.addChild(self, ch)

    def selectedAlbums(self):
        return [ch.album for ch in self.children if ch.isSelected()]


class ChildItem(TreeWidgetItem):
    def __init__(self, album, artist='', parent=None):
        self.artist = artist
        self.album = album

        TreeWidgetItem.__init__(self, parent, [album])


class LibChooseDialog(QDialog):
    """Dialog used to choose a library to load."""
    adddock = pyqtSignal(str, 'QDialog', int, name='adddock')

    def __init__(self, parent=None):
        """Dialogs that allows users to load music libraries.

        A list of libraries is listed in a ListWidget on the left with the library module's InitWidget shown on the right.

        First all libraries stored in puddlestuff.libraries are loaded.
        Then puddlestuff.musiclib.extralibs is checked for an extra libraries.
        They should already be loaded.

        

        Useful methods:
            loadLib()->Loads the currently selected library.
            loadLibConfig()

        Libraries are module which should contain the following:
            name->The name of the library.
            InitWidget class->Used to allow the use to set options required for loading the library.
        """
        QDialog.__init__(self, parent)
        self.listbox = QListWidget()
        self.setWindowTitle(translate('MusicLib', 'Import Music Library'))
        winsettings('importmusiclib', self)

        self.libattrs = []
        for libname in libraries.__all__:
            try:
                lib = __import__('puddlestuff.libraries.%s' % libname,
                                 fromlist=['puddlestuff', 'libraries'])
                if not hasattr(lib, 'InitWidget'):
                    raise Exception(translate('MusicLib', 'Invalid library'))
            except Exception as detail:
                msg = translate('MusicLib', 'Error loading %1: %2\n')
                msg = msg.arg(libname).arg(str(detail))
                sys.stderr.write(msg)
                continue

            try:
                name = lib.name
            except AttributeError:
                name = translate('MusicLib', 'Anonymous Library')

            try:
                desc = lib.description
            except AttributeError:
                desc = translate('MusicLib', 'Description was left out.')

            try:
                author = lib.author
            except AttributeError:
                author = translate('MusicLib', 'Anonymous author.')

            self.libattrs.append(
                {'name': name, 'desc': desc, 'author': author, 'module': lib})

        self.libattrs.extend(extralibs)

        if not self.libattrs:
            raise MusicLibError(0, errors[0])

        self.listbox.addItems([z['name'] for z in self.libattrs])
        self.stackwidgets = [z['module'].InitWidget() for z in self.libattrs]
        self.listbox.currentRowChanged.connect(
            self.changeWidget)

        okcancel = OKCancel()
        okcancel.ok.connect(self.loadLib)
        okcancel.cancel.connect(self.close)

        self.stack = QStackedWidget()
        self.stack.setFrameStyle(QFrame.Box)
        list(map(self.stack.addWidget, self.stackwidgets))

        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox, 0)
        hbox.addWidget(self.stack, 1)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addLayout(okcancel)

        self.setLayout(vbox)

    def changeWidget(self, number):
        if number > -1:
            self.stack.setCurrentWidget(self.stackwidgets[number])
            self.currentlib = self.libattrs[number]

    def _loadLib(self):
        try:
            return self.stack.currentWidget().library()
        except MusicLibError as details:
            return str(details.strerror)

    def loadLib(self):
        """Loads the currently selected library.

        Emits 'adddock' signal if successful with a LibraryTree class as its
        widget.
        """
        p = ProgressWin(self, 0,
                        translate('MusicLib', 'Loading music library...'), False)
        p.show()
        t = PuddleThread(self._loadLib, self)
        t.start()
        while t.isRunning():
            QApplication.processEvents()
        library = t.retval
        p.close()
        QApplication.processEvents()
        if isinstance(library, str):
            error_msg = library
            msg = translate('MusicLib',
                            'An error occured while loading the %1 library: <b>%2</b>')
            msg = msg.arg(self.currentlib['name']).arg(error_msg)

            QMessageBox.critical(self, translate('Defaults', "Error"), msg)
        else:
            dialog = partial(LibraryDialog, library)
            self.adddock.emit(
                translate('MusicLib', 'Music Library'), dialog, RIGHTDOCK)
            self.close()


class LibraryDialog(QWidget):
    """Widget containing a LibraryTree widget and searching options."""
    loadtags = pyqtSignal(list, name='loadtags')

    def __init__(self, library, parent=None, status=None):
        """Creates a library browser widget.

        Arguments:
            library->Required library class.
            parent->Parent widget.
            status->Status object."""
        QWidget.__init__(self, parent)
        if status is None:
            status = {}

        self.emits = ['loadtags']

        self.searchtext = QLineEdit()
        searchbutton = QPushButton(translate('MusicLib', '&Search'))
        self.searchtext.returnPressed.connect(
            self.searchTree)
        searchbutton.clicked.connect(
            self.searchTree)

        self._library = library
        status['library'] = library

        self.tree = LibraryTree(library)
        self.loadLib = self.tree.loadLib
        self.tree.loadtags.connect(self.loadtags)
        self.receives = [('deletedfromlib', self.tree.updateDeleted),
                         ('libfilesedited', self.tree.updateEdited)]

        searchbox = QHBoxLayout()
        searchbox.addWidget(self.searchtext)
        searchbox.addWidget(searchbutton)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addLayout(searchbox)
        vbox.addWidget(self.tree)
        self.setLayout(vbox)

    def saveSettings(self, parent=None):
        if parent is None:
            self._library.save()
        else:
            win = ProgressWin(None, 0,
                              translate('MusicLib', 'Saving music library...'),
                              False)
            win.show()
            QApplication.processEvents()
            thread = PuddleThread(lambda: self._library.save(), parent)
            thread.start()
            while thread.isRunning():
                QApplication.processEvents()
            QApplication.processEvents()
            win.close()
            QApplication.processEvents()

    def searchTree(self):
        self.tree.search(str(self.searchtext.text()))


class LibraryTree(QTreeWidget):
    loadtags = pyqtSignal(list, name='loadtags')

    def __init__(self, library, parent=None):
        QTreeWidget.__init__(self, parent)
        self.__searchResults = []

        self.setHeaderLabels([translate('MusicLib', "Library Artists")])
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.AscendingOrder)

        self.CLOSED_ICON = self.style().standardIcon(QStyle.SP_DirClosedIcon)
        self.OPEN_ICON = self.style().standardIcon(QStyle.SP_DirOpenIcon)

        self.itemCollapsed.connect(
            lambda item: item.setIcon(0, self.CLOSED_ICON))
        self.itemExpanded.connect(
            lambda item: item.setIcon(0, self.OPEN_ICON))

        self.library = library
        self.loadLib(library)

    def fillFromLib(self, library, artists=None):
        select = artists
        if not artists:
            self.clear()
            artists = library.artists
        albumslist = (library.get_albums(artist) for artist in artists)
        self.populate(zip(artists, albumslist), select)

    def getTrackFuncs(self):
        if self.__searchResults:
            st = self.__searchResults

            def get_artist_tracks(artist):
                tracks = []
                albums = st[artist]
                [tracks.extend(albums[album]) for album in albums]
                return tracks

            get_album_tracks = lambda artist, album: st[artist][album]
        else:
            _libget = self.library.get_tracks
            get_album_tracks = lambda artist, album: _libget('artist',
                                                             artist, 'album', album)
            get_artist_tracks = lambda artist: _libget('artist', artist)

        return get_album_tracks, get_artist_tracks

    def getTracks(self):

        get_album_tracks, get_artist_tracks = self.getTrackFuncs()

        total = []
        selected = self.selectedItems()

        self.blockSignals(True)
        for parent in [i for i in selected if not i.parent()]:
            [ch.setSelected(False) for ch in parent.children]
        self.blockSignals(False)

        selected = self.selectedItems()
        for item in selected:
            tracks = []
            if item.parent() and item.parent() not in selected:
                tracks = get_album_tracks(item.artist, item.album)
            else:
                tracks = get_artist_tracks(item.artist)
            total.extend(tracks)

        self.loadtags.emit(total)

    def loadLib(self, library):
        if self.library:
            self.library.close()
        self.fillFromLib(library)
        self.library = library
        self.itemSelectionChanged.disconnect(self.getTracks)
        self.itemSelectionChanged.connect(self.getTracks)

    def populate(self, data, select=False):
        icon = self.CLOSED_ICON
        for artist, albums in data:
            if not albums:
                continue

            item = ParentItem(artist, albums)
            item.setIcon(0, icon)
            self.addTopLevelItem(item)
            if select:
                item.setSelected(True)
                self.expandItem(item)

    def search(self, text):
        if not text:
            self.blockSignals(True)
            self.__searchResults = []
            self.fillFromLib(self.library)
            self.blockSignals(False)
            return

        artist_field = 'artist'
        album_field = 'album'

        tracks = self.library.search(text)
        grouped = defaultdict(lambda: defaultdict(lambda: []))

        def add_track(track):
            artist = to_string(track.get(artist_field, ''))
            album = to_string(track.get(album_field, ''))
            grouped[artist][album].append(track)

        list(map(add_track, tracks))
        self.__searchResults = grouped

        self.blockSignals(True)
        self.clear()
        self.populate(list(grouped.items()))
        self.blockSignals(False)

    def updateDeleted(self, tracks=None, artists=None):
        if self.__searchResults:
            return
        if tracks:
            data = set([to_string(track.get['artist'], '')
                        for track in tracks])
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
                remove = artist_item.removeChild

                children = artist_item.children
                toremove = [ch for ch in children if ch.album not in albums]
                [remove(child) for child in toremove]
            else:
                take_item(index(artist_item))

    def updateEdited(self, data):
        if self.__searchResults:
            return
        self.blockSignals(True)

        artists = [to_string(tag.get('artist', artist))
                   for artist, tag in data]

        self.updateDeleted(artists=[to_string(z[0]) for z in data])

        get_albums = self.library.get_albums

        newartists = []
        for artist in set(artists):
            artist_item = self.findItems(artist, Qt.MatchExactly)
            if artist_item:
                artist_item = artist_item[0]
                albums = get_albums(artist)

                tree_albums = artist_item.albums
                children = (ChildItem(album, artist, artist_item)
                            for album in albums if album not in tree_albums)

                list(map(partial(select_add_child, artist_item), children))
                self.expandItem(artist_item)
            else:
                newartists.append(artist)

        if newartists:
            self.fillFromLib(self.library, newartists)

        self.blockSignals(False)


obj = QObject()
obj.emits = ['adddock']
obj.receives = []
name = translate('MusicLib', 'Music Library')

control = (translate('MusicLib', 'Music Library'),
           LibraryDialog, RIGHTDOCK, False)

if __name__ == "__main__":
    from .libraries import quodlibetlib

    app = QApplication(sys.argv)
    lib = quodlibetlib.QuodLibet('~/.quodlibet/songs')
    qb = LibraryDialog(lib, status={})


    def b(l): print(len(l))


    qb.loadtags.connect(b)

    qb.show()
    app.exec_()
