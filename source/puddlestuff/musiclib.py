from PyQt4.QtCore import *
from PyQt4.QtGui import *
from os import path
import sys, pdb
from puddleobjects import PuddleDock, OKCancel
import audioinfo
(converttag, FILENAME, READONLY, INFOTAGS) = (audioinfo.converttag, audioinfo.FILENAME, audioinfo.READONLY, audioinfo.INFOTAGS)
import libraries, imp

class LibLoadError(Exception): pass
class LibSaveError(Exception): pass
class FileSaveError(Exception): pass
class FileWriteError(Exception): pass

class MainWin(QDialog):
    def __init__(self, parent = None):
        QDialog.__init__(self, parent)
        self.listbox = QListWidget()
        self.setWindowTitle('Import Music Library')
        self.resize(500,300)
        self.libattrs = []
        filedir = path.join(path.dirname(libraries.__file__))
        for mod in libraries.__all__:
            try: lib = imp.load_source(mod, path.join(filedir, mod + '.py'))
            except ImportError: continue

            try: name = lib.name
            except AttributeError: name = 'Anonymous Database'

            try: desc = lib.description
            except AttributeError: desc = 'Description was left out.'

            try: author = lib.author
            except AttributeError: author = 'Anonymous author.'

            self.libattrs.append({'name': name, 'desc':desc, 'author': author, 'module': lib})

        self.listbox.addItems([z['name'] for z in self.libattrs])
        self.connect(self.listbox, SIGNAL('currentRowChanged (int)'), self.loadLibConfig)

        okcancel = OKCancel()
        self.connect(okcancel, SIGNAL('ok'), self.loadLib)
        self.connect(okcancel, SIGNAL('cancel'), self.close)

        self.stack = QStackedWidget()
        self.stack.setFrameStyle(QFrame.Box)
        self.stackwidgets = {}

        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox,0)
        hbox.addWidget(self.stack,1)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addLayout(okcancel)

        self.setLayout(vbox)

    def loadLibConfig(self, number):
        if number > -1:
            if number not in self.stackwidgets:
                self.stackwidgets[number] = self.libattrs[number]['module'].ConfigWindow()
                self.stack.addWidget(self.stackwidgets[number])
            self.stack.setCurrentWidget(self.stackwidgets[number])
            self.currentlib = self.libattrs[number]

    def loadLib(self):
        try:
            self.emit(SIGNAL('libraryAvailable'), self.stack.currentWidget().setStuff())
        except Exception, details: #FIXME: Don't know why but subclassing exception doesn't work.
            QMessageBox.critical(self, "Error loading library", 'Error loading ' + self.currentlib['name'] + ": " + str(details),
             QMessageBox.Ok, QMessageBox.NoButton, QMessageBox.NoButton)
            return
        #settings = QSettings()
        #modname = self.currentlib['module'].__name__
        #modname = modname[modname.rfind('.')+1: ]
        #settings.setValue('Library/lastlib', QVariant(modname))
        #self.stack.currentWidget().saveSettings()
        self.close()

class LibraryWindow(PuddleDock):
    def __init__(self, library, loadmethod = None, parent = None):
        QDockWidget.__init__(self, "Library", parent)
        self.tree = LibraryTree(library)
        widget = QWidget(self)
        vbox = QVBoxLayout()
        vbox.setMargin(0)
        self.saveall = QPushButton('&Save')
        if hasattr(library, 'save'):
            self.connect(self.saveall, SIGNAL('clicked()'), library.save)
            self.saveall.show()
        else:
            self.saveall.hide()
        vbox.addWidget(self.saveall)
        vbox.addWidget(self.tree)
        widget.setLayout(vbox)
        self.setWidget(widget)

        if loadmethod:
            self._loadmethod = loadmethod
            self.connect(self.tree, SIGNAL("loadFiles"), loadmethod)

    def _setLoadMethod(self, value):
        self._loadmethod = value
        self.connect(self.tree, SIGNAL('loadFiles'), value)

    loadmethod = property(lambda x: self._loadmethod, _setLoadMethod)

    def loadLibrary(self, library, loadmethod):
        self.tree.loadLibrary(library)
        if hasattr(library, 'save'):
            self.saveall.show()
            self.connect(self.saveall, SIGNAL('clicked()'), library.save)
        else:
            self.saveall.hide()

        if loadmethod:
            self._loadmethod = loadmethod
            self.connect(self.tree, SIGNAL("loadFiles"), loadmethod)

class LibraryTree(QTreeWidget):
    def __init__(self, library, parent = None):
        QTreeWidget.__init__(self, parent)
        self.originals = []
        self.newfiles = []
        self.setHeaderLabels(["Library Artists"])
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.AscendingOrder)
        self.loadLibrary(library)

    def loadLibrary(self, library):
        self.clear()
        artists = library.getArtists()
        items = sorted([(artist, library.getAlbums(artist)) for artist in artists])
        icon =  self.style().standardIcon(QStyle.SP_DirClosedIcon)
        for artist, albums in items:
            if albums:
                top = QTreeWidgetItem([artist])
                top.setIcon(0, icon)
                self.addTopLevelItem(top)
                [top.addChild(QTreeWidgetItem([z])) for z in albums]

        self.connect(self, SIGNAL('itemSelectionChanged()'), self.loadFiles)
        self.connect(self, SIGNAL('itemCollapsed (QTreeWidgetItem *)'), self.setColIcon)
        self.connect(self, SIGNAL('itemExpanded (QTreeWidgetItem *)'), self.setShit)
        self.library = library

    def setColIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirClosedIcon))

    def setShit(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirOpenIcon))

    def loadFiles(self):
        total = []
        for item in self.selectedItems():
            tracks = []
            if item.parent() and item.parent() not in self.selectedItems():
                album = unicode(item.text(0))
                artist = unicode(item.parent().text(0))
                tracks = self.library.getTracks(artist, [album])
            else:
                artist = unicode(item.text(0))
                albums = [unicode(item.child(z).text(0)) for z in xrange(item.childCount())]
                tracks = self.library.getTracks(artist, albums)
            total.extend(tracks)
        tracks = []
        for z in total:
            tracks.append(Tag(self.library, z))
        self.emit(SIGNAL('loadFiles'), tracks)

    def cacheFiles(self, old, newfile = None):
        if old is True:
            self.filesEdited(self.originals, self.newfiles)
            self.originals = []
            self.newfiles = []
            return
        self.originals.extend(old)
        self.newfiles.extend(newfile)

    def filesEdited(self, originals, newfiles):
        self.blockSignals(True)
        selectedItems = []
        for y in [z for z in originals if 'artist' not in z]:
            y['artist'] = ['']
        artists = set([z['artist'][0] for z in originals])

        for artist in artists:
            try:
                item = [item for item in self.findItems(artist, Qt.MatchExactly,0)
                                                if item.childCount()][0]
            except IndexError:
                continue
            albums = self.library.getAlbums(artist)
            item.takeChildren()
            if albums:
                [item.addChild(QTreeWidgetItem([z])) for z in albums]
            else:
                self.takeTopLevelItem(self.indexOfTopLevelItem(item))

        self.scrollToItem(item)

        for y in [z for z in newfiles if 'artist' not in z]:
            y['artist'] = ['']
        artists = set([z['artist'][0] for z in newfiles])
        for artist in artists:
            albums = self.library.getAlbums(artist)
            if albums:
                items = [item for item in self.findItems(artist,
                                    Qt.MatchExactly,0) if item.childCount()]
                if items:
                    item = items[0]
                else:
                    item = QTreeWidgetItem([artist])
                    self.setColIcon(item)
                    self.addTopLevelItem(item)
                item.takeChildren()
                [item.addChild(QTreeWidgetItem([z])) for z in albums]
        self.blockSignals(False)

    def delTracks(self, tracks):
        self.blockSignals(True)
        self.library.delTracks(tracks)
        for track in tracks:
            try:
                artist = track['artist'][0]
            except KeyError:
                artist = ''
            item = [item for item in self.findItems(artist, Qt.MatchExactly,0)
                                                if item.childCount()][0]
            albums = self.library.getAlbums(artist)
            if albums:
                item.takeChildren()
                [item.addChild(QTreeWidgetItem([track])) for track in albums]
            else:
                self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        self.scrollToItem(item)
        self.blockSignals(False)


class Tag:
    def __init__(self, library, tags = None):
        self.library = library
        if tags:
            self.link(tags)

    def link(self, tags):
        self._originaltags = tags.copy()
        self.tags = {}
        for tag,value in tags.items():
            if (tag not in INFOTAGS) and (isinstance(value, (unicode, str, int, long))):
                self.tags[tag] = [value]
            else:
                self.tags[tag] = value

    def __setitem__(self, key, value):
        if key not in INFOTAGS and isinstance(value, (unicode, str, int, long)):
            self.tags[key] = [value]
            return
        self.tags[key] = value

    def __delitem__(self, key):
        if key in self.tags and key not in INFOTAGS:
            del(self.tags[key])

    def __getitem__(self, key):
        return self.tags[key]

    def __iter__(self):
        return self.tags.__iter__()

    def keys(self):
        return self.tags.keys()

    def values(self):
        return self.tags.values()

    def copy(self):
        x = Tag(self.library, self.tags.copy())
        return x

    def __contains__(self, key):
        return self.tags.__contains__(key)

    def save(self, libonly = False):
        self.library.saveTracks([(self._originaltags, self.tags)])
        toremove = [z for z in self._originaltags if z not in self.tags]
        if not libonly:
            tag = audioinfo.Tag(self[FILENAME])
            for key, value in self.tags.items():
                if isinstance(key, basestring) and not key.startswith("___"):
                    tag[key] = value
            for key in toremove:
                if key in tag:
                    del(tag[key])
            tag.save()
        self._originaltags = self.tags.copy()

    def update(self, dictionary, **kwargs):
        self.tags.update(dictionary)
        for tag,value in self.tags.items():
            if tag not in INFOTAGS and isinstance(value, (unicode, str, int, long)):
                self.tags[tag] = [value]
            else:
                self.tags[tag] = value

    def stringtags(self):
        return converttag(self)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    qb = MainWin()
    qb.show()
    app.exec_()