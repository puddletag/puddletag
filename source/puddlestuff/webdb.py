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
from puddleobjects import unique, OKCancel, PuddleThread, PuddleConfig
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from collections import defaultdict
import plugins
import puddlestuff.tagsources.musicbrainz as mbrainz
from puddlestuff.tagsources import RetrievalError
from puddlestuff.constants import TEXT, COMBO, CHECKBOX, RIGHTDOCK
pyqtRemoveInputHook()
from findfunc import replacevars, getfunc

def display_tag(tag):
    """Used to display tags in the status bar in a human parseable format."""
    if not tag:
        return "<b>Error in pattern</b>"
    s = "<b>%s</b>: %s, "
    tostr = lambda i: i if isinstance(i, basestring) else i[0]
    return "<br />".join([s % (z, tostr(v)) for z, v in sorted(tag.items())])[:-2]

def display(pattern, tags):
    return replacevars(getfunc(pattern, tags), tags)

class TagListWidget(QWidget):
    def __init__(self, tags=None, parent=None):
        QWidget.__init__(self, parent)
        if not tags:
            tags = []
        label = QLabel()
        label.setText('&Tags')
        self._text = QLineEdit(u', '.join(tags))
        label.setBuddy(self._text)

        layout = QHBoxLayout()
        layout.setMargin(0)
        layout.addWidget(label, 0)
        layout.addWidget(self._text, 1)

        self.connect(self._text, SIGNAL('textChanged(QString)'), self.emitTags)

        self.setLayout(layout)

    def tags(self, text=None):
        if text is None:
            return [z.strip() for z in unicode(self._text.text()).split(u',')]
        else:
            return [z.strip() for z in unicode(text).split(u',')]

    def emitTags(self, text=None):
        self.emit(SIGNAL('tagschanged'), self.tags(text))

    def setTags(self, tags):
        self._text.setText(u', '.join(tags))

class SourcePrefs(QDialog):
    def __init__(self, controls, parent = None):
        QDialog.__init__(self, parent)
        vbox = QVBoxLayout()
        self._controls = []
        for desc, ctype, default in controls:
            if ctype == TEXT:
                control = QLineEdit(default)
                label = QLabel(desc)
                label.setBuddy(control)
                vbox.addWidget(label)
                vbox.addWidget(control)
            elif ctype == COMBO:
                control = QComboBox()
                control.addItems(default)
                label = QLabel(desc)
                label.setBuddy(control)
                vbox.addWidget(label)
                vbox.addWidget(control)
            elif ctype == CHECKBOX:
                control = QCheckBox(desc)
                if default:
                    control.setCheckState(Qt.Checked)
                else:
                    control.setCheckState(Qt.Unchecked)
                vbox.addWidget(control)
            self._controls.append(control)
        okcancel = OKCancel()
        self.connect(okcancel, SIGNAL('ok'), self.okClicked)
        self.connect(okcancel, SIGNAL('cancel'), self.close)
        vbox.addLayout(okcancel)
        vbox.addStretch()
        self.setLayout(vbox)

    def okClicked(self):
        values = []
        for control in self._controls:
            if isinstance(control, QLineEdit):
                values.append(unicode(control.text()))
            elif isinstance(control, QComboBox):
                values.append(control.currentIndex())
            elif isinstance(control, QCheckBox):
                values.append(bool(control.checkState()))
        self.emit(SIGNAL('tagsourceprefs'), values)
        self.close()


class SettingsDialog(QWidget):
    def __init__(self, parent = None, status = None):
        QWidget.__init__(self, parent)
        self.title = 'Tag Sources'
        label = QLabel('&Display format for individual tracks.')
        cparser = PuddleConfig()
        text = cparser.get('tagsources', 'displayformat', '%track% - %title%')
        self._text = QLineEdit(text)
        label.setBuddy(self._text)
        vbox = QVBoxLayout()
        vbox.addWidget(label)
        vbox.addWidget(self._text)
        vbox.addStretch()
        self.setLayout(vbox)

    def applySettings(self, control):
        text = unicode(self._text.text())
        control.listbox.dispformat = text
        cparser = PuddleConfig()
        cparser.set('tagsources', 'displayformat', text)

class ChildItem(QTreeWidgetItem):
    def __init__(self, dispformat, track, *args):
        QTreeWidgetItem.__init__(self, *args)
        self.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
                        | Qt.ItemIsSelectable)
        self.track = track
        self.dispformat = dispformat
        self.setToolTip(0, display_tag(track))

    def _setPattern(self, val):
        self.setText(0, display(val, self.track))
        self._dispformat = val

    def _getPattern(self):
        return self._dispformat

    dispformat = property(_getPattern, _setPattern)

class ReleaseWidget(QTreeWidget):
    def __init__(self, status, tagsource, parent = None):
        QTreeWidget.__init__(self, parent)
        self._dispformat = u'%track% - %title%'
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setSelectionMode(self.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(self.InternalMove)
        self._artists = {}
        self._albums = []
        self._tracks = {}
        self._dirtyrow = 0
        self._status = status
        self._tagsource = tagsource
        self.tagstowrite = []

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
            for parent in toplevels:
                child = parent.child
                [child(row).setSelected(False) for row in
                    range(parent.childCount())]
            toprows = [rowindex(z) for z in toplevels]
            t = [z for z in toprows if z not in self._tracks]
            if t:
                self.gettracks(t)
                return
        self._selectedTracks()
        #self.emit(SIGNAL("statusChanged"), "Selection changed.")

    def _children(self, item):
        child = item.child
        return [child(row) for row in xrange(item.childCount())]

    def _selectedTracks(self):
        rowindex = self.indexOfTopLevelItem
        selected = self.selectedItems()
        #tracks = []
        toplevels = [z for z in selected if not z.parent()]
        if toplevels:
            children = [z for z in selected if z.parent() and z.parent() not in toplevels]
            [children.extend(self._children(parent)) for parent in toplevels]
        else:
            children = selected

        tracks = [child.track for child in children]
        if self.tagstowrite:
            def strip(audio, taglist):
                return dict([(key, audio[key]) for key in taglist if key in audio])
            tags = self.tagstowrite
            tracks = [strip(track, tags) for track in tracks]
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
        for artist, albums in sorted(releases.items()):
            if '__albumlist' in albums:
                albums = albums['__albumlist']
            for album, tracks in sorted(albums.items()):
                self.addTopLevelItem(item(u'%s - %s' % (artist, album)))
                if tracks:
                    row = len(self._artists)
                    self._tracks[len(self._artists)] = tracks
                    self._addTracks(row, tracks)
                self._artists.append(artist)
                self._albums.append(album)

    def _addTracks(self, row, tracks):
        item = self.topLevelItem(row)
        item.takeChildren()
        item.setText(0, item.text(0) + ' [%d]' % len(tracks[0]))
        [item.addChild(ChildItem(self.dispformat, z))
            for z in tracks[0]]

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

    def _getDispFormat(self):
        return self._dispformat

    def _setDispFormat(self, val):
        self._dispformat = val
        iterator = QTreeWidgetItemIterator(self,
                        QTreeWidgetItemIterator.NoChildren)
        while iterator.value():
            item = iterator.value()
            item.dispformat = val
            iterator += 1

    dispformat = property(_getDispFormat, _setDispFormat)

class MainWin(QWidget):
    def __init__(self, status, parent = None):
        QWidget.__init__(self, parent)
        self.settingsdialog = SettingsDialog
        self.emits = ['writepreview', 'setpreview', 'clearpreview']
        self.receives = []
        self.setWindowTitle("Tag Sources")
        self._status = status
        tagsources = [mbrainz]
        tagsources.extend(plugins.tagsources)
        self._tagsources = [module.info[0]() for module in tagsources]
        self._configs = [module.info[1] for module in tagsources]
        self._tagsource = self._tagsources[0]
        self._tagstowrite = [[] for z in self._tagsources]
        self._sourcenames = [z.name for z in tagsources]
        self._lastindex = 0

        self.sourcelist = QComboBox()
        self.sourcelist.addItems(self._sourcenames)
        self.connect(self.sourcelist, SIGNAL('currentIndexChanged (int)'),
                        self._changeSource)
        sourcelabel = QLabel('Sour&ce: ')
        sourcelabel.setBuddy(self.sourcelist)

        preferences = QToolButton()
        preferences.setIcon(QIcon(':/preferences.png'))
        preferences.setToolTip('Configure')
        self.connect(preferences, SIGNAL('clicked()'), self.configure)

        sourcebox = QHBoxLayout()
        sourcebox.addWidget(sourcelabel)
        sourcebox.addWidget(self.sourcelist, 1)
        sourcebox.addWidget(preferences)

        self._searchparams = QLineEdit()
        tooltip = "Enter search parameters here. If empty, the selected files are used. <ul><li><b>artist;album</b> searches for a specific album/artist combination.</li> <li>For multiple artist/album combinations separate them with the '|' character. eg. <b>Amy Winehouse;Back To Black|Outkast;Atliens</b>.</li> <li>To list the albums by an artist leave off the album part, but keep the semicolon (eg. <b>Ratatat;</b>). For a album only leave the artist part as in <b>;Resurrection.</li></ul>"
        self._searchparams.setToolTip(tooltip)

        self.getinfo = QPushButton("&Search")
        self.getinfo.setDefault(True)
        self.getinfo.setAutoDefault(True)
        self.connect(self._searchparams, SIGNAL('returnPressed()'), self.getInfo)
        self.connect(self.getinfo , SIGNAL("clicked()"), self.getInfo)

        self._writebutton = QPushButton('&Write')
        self._writebutton.setEnabled(False)
        clear = QPushButton("Clea&r preview")

        self.connect(self._writebutton, SIGNAL("clicked()"), self._write)
        self.connect(clear, SIGNAL("clicked()"), self._clear)

        self.label = QLabel("Select files and click on Search to retrieve "
                            "metadata.")

        self.listbox = ReleaseWidget(status, self._tagsource)

        self._taglist = TagListWidget()
        self.connect(self._taglist, SIGNAL('tagschanged'), self._changeTags)
        self.connect(self.listbox, SIGNAL('statusChanged'), self.label.setText)
        self.connect(self.listbox, SIGNAL('itemSelectionChanged()'),
                        self._enableWrite)
        self.connect(self.listbox, SIGNAL('preview'),
                        lambda tags: self.emit(SIGNAL('setpreview'), tags))
        hbox = QHBoxLayout()
        hbox.addWidget(self._searchparams, 1)
        hbox.addWidget(self.getinfo, 0)

        vbox = QVBoxLayout()
        vbox.addLayout(sourcebox)
        vbox.addLayout(hbox)
        vbox.addWidget(self.label)
        vbox.addWidget(self.listbox, 1)
        hbox = QHBoxLayout()
        hbox.addWidget(self._taglist, 1)
        hbox.addStretch()
        hbox.addWidget(self._writebutton)
        hbox.addWidget(clear)
        vbox.addLayout(hbox)

        self.setLayout(vbox)
        self._changeSource(0)

    def _clear(self):
        self.emit(SIGNAL('clearpreview'))

    def _changeSource(self, index):
        self._tagsource = self._tagsources[index]
        self.listbox._tagsource = self._tagsource
        if hasattr(self._tagsource, 'preferences'):
            self._config = self._tagsource.preferences
        else:
            self._config = self._configs[index]
        self._lastindex = index
        self._taglist.setTags(self._tagstowrite[index])

    def _changeTags(self, tags):
        self.listbox.tagstowrite = tags
        self.listbox._selectedTracks()
        self._tagstowrite[self._lastindex] = tags

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
        self.label.setText('Retrieving album info.')
        if self._searchparams.text():
            text = unicode(self._searchparams.text())
            params = defaultdict(lambda:[])
            try:
                text = [z.split(';') for z in text.split(u'|') if z]
                [params[z.strip()].append(v.strip()) for z, v in text]
            except ValueError:
                self.label.setText('<b>Error parsing artist/album combinations.</b>')
                self.getinfo.setEnabled(True)
                return
        else:
            if not tags:
                self.label.setText('<b>Select some files or enter search paramaters.</b>')
                return
            params = None

        def retrieve():
            try:
                if params:
                    return self._tagsource.search(params=params)
                else:
                    return self._tagsource.search(audios=tags)
            except RetrievalError, e:
                return 'An error occured: %s' % unicode(e)
        self.getinfo.setEnabled(False)
        self._t = PuddleThread(retrieve)
        self.connect(self._t, SIGNAL('threadfinished'), self.setInfo)
        self._writebutton.setEnabled(False)
        self._t.start()

    def configure(self):
        config = self._config
        if config is None:
            return
        if isinstance(config, QDialog):
            win = config(parent=self)
        else:
            win = SourcePrefs(config, self)
        win.setModal(True)
        self.connect(win, SIGNAL('tagsourceprefs'), self._tagsource.applyPrefs)
        win.show()

    def setInfo(self, releases):
        self.getinfo.setEnabled(True)
        if isinstance(releases, basestring):
            self.label.setText(releases)
        else:
            self.listbox.setReleases(releases)
            found = []
            notfound = []
            for artist, values in releases.items():
                if not values.get('__albumlist') and len(values) <= 1:
                    notfound.append(artist)
                else:
                    found.append(artist)
            foundtext = u'Albums retrieved for %s.' % u', '.join(found)
            notfoundtext = u'No albums found for %s.' % u', '.join(notfound)
            if found and notfound:
                text = u'%s<br />%s' % (foundtext, notfoundtext)
            elif found:
                text = foundtext
            else:
                text = notfoundtext
            self.label.setText(text)

    def loadSettings(self):
        settings = PuddleConfig()
        source = settings.get('tagsources', 'lastsource', 'Musicbrainz')
        self._tagstowrite = [settings.get('tagsourcetags', name , []) for
                                name in self._sourcenames]
        index = self.sourcelist.findText(source)
        self.sourcelist.setCurrentIndex(index)
        self._taglist.setTags(self._tagstowrite[index])
        df = settings.get('tagsources', 'displayformat', u'%track% - %title%')
        self.listbox.dispformat = df

    def saveSettings(self):
        settings = PuddleConfig()
        settings.set('tagsources', 'lastsource', self.sourcelist.currentText())
        for i, name in enumerate(self._sourcenames):
            settings.set('tagsourcetags', name , self._tagstowrite[i])

control = ('Tag Sources', MainWin, RIGHTDOCK, False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    status = {}
    status['selectedfiles'] = exampletags.tags
    win = MainWin(status)
    win.show()
    app.exec_()