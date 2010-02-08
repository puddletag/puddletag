#! /usr/bin/env python
#webdb.py

#Copyright (C) 2008-2009 concentricpuddle

#This file is part of puddletag, a semi-good music tag editor.

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
import sys, pdb
from puddleobjects import unique, OKCancel, PuddleThread, winsettings
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from collections import defaultdict

import puddlestuff.tagsources.musicbrainz as mbrainz
from puddlestuff.tagsources import RetrievalError
from puddlestuff.tagsources import exampletags
pyqtRemoveInputHook()

class ReleaseWidget(QTreeWidget):
    def __init__(self, status, tagsource, parent = None):
        QTreeWidget.__init__(self, parent)

        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setSelectionMode(self.ExtendedSelection)
        self._artists = {}
        self._albums = []
        self._tracks = {}
        self._dirtyrow = 0
        self._status = status
        self._tagsource = tagsource

        connect = lambda signal, slot: self.connect(self, SIGNAL(signal), slot)
        connect('itemSelectionChanged()', self._selChanged)
        connect('itemCollapsed (QTreeWidgetItem *)', self.setClosedIcon)
        connect('itemExpanded (QTreeWidgetItem *)', self.setOpenIcon)

    def setClosedIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirClosedIcon))

    def setOpenIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirOpenIcon))
        row = self.indexOfTopLevelItem(item)
        if row not in self._tracks:
            self.gettracks([row])

    def _selChanged(self):
        rowindex = self.indexOfTopLevelItem
        toplevels = [z for z in self.selectedItems() if not z.parent()]
        if toplevels:
            toprows = [rowindex(z) for z in toplevels]
            t = [z for z in toprows if z not in self._tracks]
            if t:
                self.gettracks(t)
                return
        self._selectedTracks()
        #self.emit(SIGNAL("statusChanged"), "Selection changed.")

    def _selectedTracks(self):
        rowindex = self.indexOfTopLevelItem
        selected = self.selectedItems()
        tracks = []
        toplevels = [z for z in selected if not z.parent()]
        if toplevels:
            children = [z for z in selected if z.parent() and z.parent() not in toplevels]
            toprows = [rowindex(z) for z in toplevels]
            [tracks.extend(self._tracks[z][0]) for z in toprows]
        else:
            children = selected

        for child in children:
            parent = child.parent()
            tracks.append(self._tracks[rowindex(parent)][0][parent.indexOfChild(child)])
        self.emit(SIGNAL('preview'), tracks[:len(self._status['selectedrows'])])

    def gettracks(self, rows):
        try:
            while self.t.isRunning():
                pass
        except AttributeError:
            pass
        topitem = self.topLevelItem
        self.emit(SIGNAL("statusChanged"), "Retrieving album tracks...")
        QApplication.processEvents()
        def func():
            ret = {}
            for row in rows:
                if row in self._tracks:
                    ret[row] = self._tracks[row]
                else:
                    artist = self._artists[row]
                    album = self._albums[row]
                    self.emit(SIGNAL("statusChanged"),
                                u'Retrieving: <b>%s</b>' % topitem(row).text(0))
                    ret[row] = self._tagsource.retrieve(artist, album)
            return ret
        self.t = PuddleThread(func)
        self.connect(self.t, SIGNAL("threadfinished"), self.updateStatus)
        self.t.start()

    def setReleases(self, releases):
        self.clear()
        self._tracks = {}
        self._artists = []
        self._albums = []
        def item(text):
            item = QTreeWidgetItem([text])
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            item.setIcon(0,self.style().standardIcon(QStyle.SP_DirClosedIcon))
            return item
        for artist, albums in releases.items():
            if '__albumlist' in albums:
                albums = albums['__albumlist']
            for album, tracks in albums.items():
                self.addTopLevelItem(item('%s - %s' % (artist, album)))
                if tracks:
                    row = len(self._artists)
                    self._tracks[len(self._artists)] = tracks
                    self._addTracks(row, tracks)
                self._artists.append(artist)
                self._albums.append(album)

    def _addTracks(self, row, tracks):
        item = self.topLevelItem(row)
        item.takeChildren()
        item.setText(0, item.text(0) + '[%d]' % len(tracks[0]))
        [item.addChild(QTreeWidgetItem([z['title']])) for z in tracks[0]]

    def updateStatus(self, val):
        if not val:
            self.emit(SIGNAL("statusChanged"), 'An unexpected error occurred.')
            return
        for row, tracks in val.items():
            if row in self._tracks:
                continue
            self._tracks[row] = tracks
            self._addTracks(row, tracks)
        self.emit(SIGNAL("statusChanged"), "Track retrieval successful.")
        self._selectedTracks()

class MainWin(QDialog):
    def __init__(self, status, parent = None):
        QDialog.__init__(self, parent)
        self.emits = ['writepreview', 'setpreview']
        self.receives = []
        self.setWindowTitle("puddletag Musicbrainz")
        self._status = status
        self._tagsource = mbrainz.MusicBrainz()
        #winsettings('tagsources', self)

        self._searchparams = QLineEdit()
        tooltip = "Enter search parameters here. If empty, the selected files are used. <ul><li><b>artist;album</b> searches for a specific album/artist combination.</li> <li>For multiple artist/album combinations separate them with the '|' character. eg. <b>Amy Winehouse;Back To Black|Outkast;Atliens</b>.</li> <li>To list the albums by an artist leave off the album part, but keep the semicolon (eg. <b>Ratatat;</b>). For a album only leave the artist part as in <b>;Resurrection.</li></ul>"
        self._searchparams.setToolTip(tooltip)

        self.getinfo = QPushButton("Search")
        self.connect(self.getinfo , SIGNAL("clicked()"), self.getInfo)

        self._writebutton = QPushButton('&Write')
        clear = QPushButton("Clea&r tags")

        self.connect(self._writebutton, SIGNAL("clicked()"), self._write)
        self.connect(clear, SIGNAL("clicked()"), self._clear)

        self.label = QLabel("Select files and click on Search to retrieve "
                            "metadata.")

        self.listbox = ReleaseWidget(status, self._tagsource)
        self.connect(self.listbox, SIGNAL('statusChanged'), self.label.setText)
        self.connect(self.listbox, SIGNAL('itemSelectionChanged()'),
                        self._enableWrite)
        self.connect(self.listbox, SIGNAL('preview'),
                        lambda tags: self.emit(SIGNAL('setpreview'), tags))
        hbox = QHBoxLayout()
        hbox.addWidget(self._searchparams, 1)
        hbox.addWidget(self.getinfo, 0)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.label)
        vbox.addWidget(self.listbox, 1)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._writebutton)
        hbox.addWidget(clear)
        vbox.addLayout(hbox)

        self.setLayout(vbox)
        self.show()

    def _clear(self):
        self.emit(SIGNAL('clearpreview'))

    def _enableWrite(self):
        if self.listbox.selectedItems():
            self._writebutton.setEnabled(True)
        else:
            self._writebutton.setEnabled(False)

    def _write(self):
        self.emit(SIGNAL('writepreview'))
        self.label.setText("<b>Tags were written.</b>")

    def closeEvent(self, e):
        self._clear()

    def getInfo(self):
        tags = self._status['selectedfiles']
        self.getinfo.setEnabled(False)
        self.label.setText('Retrieving album info.')
        if self._searchparams:
            text = unicode(self._searchparams.text())
            params = defaultdict(lambda:[])
            try:
                text = [z.split(';') for z in text.split(u'|') if z]
                [params[z.strip()].append(v.strip()) for z, v in text]
            except ValueError:
                self.label.setText('<b>Error parsing artist/album combinations</b>')
                self.getinfo.setEnabled(True)
                return
        else:
            params = None
        def retrieve():
            try:
                if params:
                    return self._tagsource.search(params=params)
                else:
                    return self._tagsource.search(audios=tags)
                #f = '/home/keith/Documents/python/puddletag/puddlestuff/releases'
                #return pickle.load(open(f, 'rb'))
            except RetrievalError, e:
                return 'An error occured: %s', unicode(e)
        self._t = PuddleThread(retrieve)
        self.connect(self._t, SIGNAL('threadfinished'), self.setInfo)
        self._writebutton.setEnabled(False)
        self._t.start()

    def setInfo(self, releases):
        self.getinfo.setEnabled(True)
        if isinstance(releases, basestring):
            self.label.setText(releases)
        else:
            self.listbox.setReleases(releases)
            self.label.setText('Albums retrieved.')

control = ('MusicBrainz', MainWin)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    status = {}
    status['selectedfiles'] = exampletags.tags
    win = MainWin(status)
    win.show()
    app.exec_()