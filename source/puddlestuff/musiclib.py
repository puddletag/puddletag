from PyQt4.QtCore import *
from PyQt4.QtGui import *
from os import path
import sys, pdb
from puddleobjects import PuddleDock, OKCancel
import audioinfo
(converttag, FILENAME, READONLY, INFOTAGS) = (audioinfo.converttag, audioinfo.FILENAME, audioinfo.READONLY, audioinfo.INFOTAGS)
import libraries, imp

class MusicLibError(Exception):
    def __init__(self, number, stringvalue):
        self.strerror = stringvalue
        self.number = number
errors = {
    0: "Library load error",
    1: "Library save error",
    2: "Library file load error",
    3: "Library file save error"}

class MainWin(QDialog):
    def __init__(self, parent = None):
        QDialog.__init__(self, parent)
        self.listbox = QListWidget()
        self.setWindowTitle('Import Music Library')
        self.resize(550,300)

        self.libattrs = []
        filedir = path.join(path.dirname(libraries.__file__))
        for mod in libraries.__all__:
            try:
                lib = imp.load_source(mod, path.join(filedir, mod + '.py'))
            except ImportError, detail:
                sys.stderr.write(u'Error loading %s: %s\n' % (mod, unicode(detail)))
                continue

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
            self.emit(SIGNAL('libraryAvailable'), self.stack.currentWidget().getLibClass())
        except MusicLibError, details:
            QMessageBox.critical(self, u"Error", u'I encountered an error while loading %s: <b>%s</b>' \
                            % (unicode(self.currentlib['name']), unicode(details.strerror)),
                            QMessageBox.Ok, QMessageBox.NoButton, QMessageBox.NoButton)
            return
        settings = QSettings()
        modname = self.currentlib['module'].__name__
        modname = modname[modname.rfind('.')+1: ]
        settings.setValue('Library/lastlib', QVariant(modname))
        self.stack.currentWidget().saveSettings()
        self.close()

class LibraryWindow(PuddleDock):
    def __init__(self, library, loadmethod = None, parent = None):
        QDockWidget.__init__(self, "Library", parent)
        self.tree = LibraryTree(library)
        widget = QWidget(self)
        vbox = QVBoxLayout()
        vbox.setMargin(0)
        hbox = QHBoxLayout()
        self.saveall = QPushButton('&Save')
        hbox.addWidget(self.saveall)
        hbox.addStretch()
        if hasattr(library, 'save'):
            self.connect(self.saveall, SIGNAL('clicked()'), library.save)
            self.saveall.show()
        else:
            self.saveall.hide()

        searchlabel = QLabel('&Search')
        searchtext = QLineEdit()
        self.connect(searchtext, SIGNAL('textChanged(const QString&)'),
                self.tree.search)
        searchlabel.setBuddy(searchtext)
        searchbox = QHBoxLayout()
        searchbox.addWidget(searchlabel)
        searchbox.addWidget(searchtext)

        vbox.addLayout(hbox)
        vbox.addLayout(searchbox)
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
        self.lastsearch = ""

    def loadLibrary(self, library):
        if hasattr(self, 'library'):
            self.library.close()
        self.fillTree(library)
        self.library = library
        self.disconnect(self, SIGNAL('itemSelectionChanged()'), self.loadSearch)
        self.connect(self, SIGNAL('itemSelectionChanged()'), self.loadFiles)

    def fillTree(self, library):
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
        self.connect(self, SIGNAL('itemCollapsed (QTreeWidgetItem *)'), self.setClosedIcon)
        self.connect(self, SIGNAL('itemExpanded (QTreeWidgetItem *)'), self.setOpenIcon)


    def setClosedIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirClosedIcon))

    def setOpenIcon(self, item):
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
        self.emit(SIGNAL('loadFiles'), total)

    def cacheFiles(self, old, newfile = None):
        if old is True:
            self.filesEdited(self.originals, self.newfiles)
            self.originals = []
            self.newfiles = []
            return
        self.originals.extend(old)
        self.newfiles.extend(newfile)

    def treedata(self, tracks):
        ret = {}
        for track in tracks:
            try:
                artist = track['artist'][0]
            except KeyError:
                track['artist'] = ['']
                artist = ''

            try:
                album = track['album'][0]
            except KeyError:
                album = ''
                track['album'] = ['']

            if artist in ret:
                if album not in ret[artist]:
                    ret[artist].add(album)
            else:
                ret[artist] = set([album])
        return ret

    def addData(self, data):
        for artist in data:
            item = QTreeWidgetItem([artist])
            self.addTopLevelItem(item)
            [item.addChild(QTreeWidgetItem([child])) for child in data[artist]]
            self.setClosedIcon(item)

    def removeDefunct(self, artist, albums):
        item = [item for item in self.findItems(artist, Qt.MatchExactly,0)
                                                    if item.childCount()][0]

        if not albums:
            self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        else:
            toremove = []
            for i in xrange(item.childCount()):
                text = unicode(item.child(i).text(0))
                if text not in albums:
                    toremove.append(i)
            temp = toremove[:]
            for i in range(len(toremove)):
                item.takeChild(temp[i])
                QApplication.processEvents()
                temp = [z-1 for z in temp]
            if not item.childCount():
                self.takeTopLevelItem(item)

    def filesEdited(self, originals, newfiles):
        self.blockSignals(True)
        old, new = self.treedata(originals), self.treedata(newfiles)
        if self.lastsearch:
            filenames = [z[FILENAME] for z in self.searchfiles]
            for f,n in zip(originals, newfiles):
                index = filenames.index(f[FILENAME])
                self.searchfiles[index] = n
            data = self.treedata(self.searchfiles)

        for artist in old:
            if self.lastsearch:
                try:
                    albums = data[artist]
                except KeyError:
                    albums = []
            else:
                albums = self.library.getAlbums(artist)
            self.removeDefunct(artist, albums)

        toselect = []
        for artist in new:
            items = [item for item in self.findItems(artist, Qt.MatchExactly,0)
                                                    if item.childCount()]
            if items:
                item = items[0]
                oldalbums = [unicode(item.child(z).text(0))
                                for z in range(item.childCount())]
                for album in new[artist]:
                    if album in oldalbums:
                        child = item.child(oldalbums.index(album))
                    else:
                        child = QTreeWidgetItem([album])
                        item.addChild(child)
                    toselect.append(child)
                self.expandItem(item)
                QApplication.processEvents()
                [self.setItemSelected(z, True) for z in toselect]
                QApplication.processEvents()
            else:
                item = QTreeWidgetItem([artist])
                self.addTopLevelItem(item)
                [item.addChild(QTreeWidgetItem([album])) for album in new[artist]]
                QApplication.processEvents()
                self.setOpenIcon(item)
                self.expandItem(item)
                QApplication.processEvents()
                self.setItemSelected(item, True)
                QApplication.processEvents()
        self.blockSignals(False)

    def fillTracks(self, tracks):
        self.clear()
        treedata = self.treedata(tracks)
        self.addData(treedata)

    def delTracks(self, tracks):
        self.blockSignals(True)
        self.library.delTracks(tracks)
        if self.lastsearch:
            filenames = [z[FILENAME] for z in self.searchfiles]
            toremove = []
            for f in tracks:
                toremove.append(filenames.index(f[FILENAME]))
            for index in range(len(toremove[:])):
                del(self.searchfiles[toremove[index]])
                toremove = [z-1 for z in toremove]
            data = self.treedata(self.searchfiles)
        for artist in self.treedata(tracks):
            if self.lastsearch:
                try:
                    albums = data[artist]
                except KeyError:
                    albums = []
            else:
                albums = self.library.getAlbums(artist)
            self.removeDefunct(artist, albums)
        self.blockSignals(False)

    def search(self, text):
        text = unicode(text)
        self.lastsearch = text
        self.blockSignals(True)
        if not text:
            self.connect(self, SIGNAL('itemSelectionChanged()'), self.loadFiles)
            self.fillTree(self.library)
            return
        text = unicode(text)
        self.disconnect(self, SIGNAL('itemSelectionChanged()'), self.loadFiles)
        self.searchfiles = self.library.search(text)
        self.fillTracks(self.searchfiles)

        self.connect(self, SIGNAL('itemSelectionChanged()'), self.loadSearch)
        self.blockSignals(False)

    def loadSearch(self):
        total = []
        for item in self.selectedItems():
            tracks = []
            if item.parent() and item.parent() not in self.selectedItems():
                album = unicode(item.text(0))
                artist = unicode(item.parent().text(0))
                tracks = [z.copy() for z in self.searchfiles if z['artist'][0] == artist and z['album'][0] == album]
            else:
                artist = unicode(item.text(0))
                albums = [unicode(item.child(z).text(0)) for z in xrange(item.childCount())]
                tracks = [z.copy() for z in self.searchfiles if z['artist'][0] == artist]
            total.extend(tracks)
        self.emit(SIGNAL('loadFiles'), total)

class Tag:
    def __init__(self, library, tags = None):
        self.library = library
        if tags:
            self.link(tags)

    def link(self, tags):
        self._originaltags = tags.copy()
        self.tags = {}
        for tag,value in tags.items():
            if (tag not in INFOTAGS) and (isinstance(value, (basestring, int, long))):
                self.tags[tag] = [value]
            else:
                self.tags[tag] = value

    def __setitem__(self, key, value):
        if key not in INFOTAGS and isinstance(value, (basestring, int, long)):
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
        return Tag(self.library, self.tags.copy())

    def __contains__(self, key):
        return self.tags.__contains__(key)

    def save(self, libonly = False):
        self.library.saveTracks([(self._originaltags, self.tags)])
        toremove = [z for z in self._originaltags if z not in self.tags]
        if not libonly:
            tag = audioinfo.Tag(self[FILENAME])
            if not tag:
                raise OSError(2, u"Couldn't read file: '%s'" % self[FILENAME])
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

    def items(self):
        return self.tags.items()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    qb = MainWin()
    qb.show()
    app.exec_()