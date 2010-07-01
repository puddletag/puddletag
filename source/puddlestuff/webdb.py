#! /usr/bin/env python
# -*- coding: utf-8 -*-
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
import sys, pdb, os
from puddleobjects import (unique, OKCancel, PuddleThread, PuddleConfig, 
    winsettings, ListBox, ListButtons, OKCancel)
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from collections import defaultdict
import plugins
import puddlestuff.tagsources.musicbrainz as mbrainz
import puddlestuff.tagsources.freedb as freedb
import puddlestuff.tagsources.amazon as amazon
try:
    import puddlestuff.tagsources.amg as allmusic
except ImportError:
    allmusic = None
import puddlestuff.tagsources as tagsources
from puddlestuff.tagsources import RetrievalError, status_obj, write_log
from puddlestuff.constants import TEXT, COMBO, CHECKBOX, RIGHTDOCK, SAVEDIR
pyqtRemoveInputHook()
from findfunc import replacevars, getfunc
from functools import partial
from copy import copy
from puddlestuff.util import to_string
from releasewidget import ReleaseWidget

def display_tag(tag):
    """Used to display tags in in a human parseable format."""
    if not tag:
        return "<b>Error in pattern</b>"
    s = "<b>%s</b>: %s"
    tostr = lambda i: i if isinstance(i, basestring) else i[0]
    if ('__image' in tag) and tag['__image']:
        d = {'#images': unicode(len(tag['__image']))}
    else:
        d = {}
    return "<br />".join([s % (z, tostr(v)) for z, v in
                    sorted(tag.items() + d.items()) if z != '__image' and not
                    z.startswith('#')])

def display(pattern, tags):
    return replacevars(getfunc(pattern, tags), tags)

def strip(audio, taglist, reverse = False):
    if not taglist:
        return dict([(key, audio[key]) for key in audio if 
                        not key.startswith('#')])
    tags = taglist[::]
    if tags and tags[0].startswith('~'):
        reverse = True
        tags[0] = tags[0][1:]
    else:
        reverse = False
    if reverse:
        return dict([(key, audio[key]) for key in audio if key not in
                        tags and not key.startswith('#')])
    else:
        return dict([(key, audio[key]) for key in taglist if key in audio and
            not key.startswith('#')])

def split_strip(stringlist):
    return [[field.strip() for field in s.split(u',')] for s in stringlist]

class TagListWidget(QWidget):
    def __init__(self, tags=None, parent=None):
        QWidget.__init__(self, parent)
        if not tags:
            tags = []
        label = QLabel()
        label.setText('&Fields')
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
        
    def setToolTip(self, value):
        QWidget.setToolTip(self, value)
        self._text.setToolTip(value)

class SourcePrefs(QDialog):
    def __init__(self, title, controls, parent = None):
        QDialog.__init__(self, parent)
        vbox = QVBoxLayout()
        self._controls = []
        winsettings(title, self)
        self.setWindowTitle(u'Configure: ' + title)
        for desc, ctype, default in controls:
            if ctype == TEXT:
                control = QLineEdit(default)
                label = QLabel(desc)
                label.setBuddy(control)
                vbox.addWidget(label)
                vbox.addWidget(control)
            elif ctype == COMBO:
                control = QComboBox()
                control.addItems(default[0])
                control.setCurrentIndex(default[1])
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


class SortOptionEditor(QDialog):
    def __init__(self, options, parent = None):
        QDialog.__init__(self, parent)
        connect = lambda c, signal, s: self.connect(c, SIGNAL(signal), s)
        self.listbox = ListBox()
        self.listbox.setSelectionMode(self.listbox.ExtendedSelection)
        buttons = ListButtons()

        self.listbox.addItems(options)
        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox,1)

        hbox.addLayout(buttons)
        
        okcancel = OKCancel()
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addLayout(okcancel)
        self.setLayout(vbox)

        connect(buttons, "add", self.addPattern)
        connect(buttons, "edit", self.editItem)
        buttons.duplicate.setVisible(False)
        self.connect(okcancel, SIGNAL('ok'), self.applySettings)
        self.connect(okcancel, SIGNAL('cancel'), self.applySettings)
        self.listbox.connectToListButtons(buttons)
        self.listbox.editButton = buttons.edit
        connect(self.listbox, 'itemDoubleClicked(QListWidgetItem *)',
                    self._doubleClicked)

    def addPattern(self):
        l = self.listbox.item
        patterns = [unicode(l(z).text()) for z in range(self.listbox.count())]
        row = self.listbox.currentRow()
        if row < 0:
            row = 0
        (text, ok) = QInputDialog().getItem(self, 'Add', 
            'Enter a sorting option (a comma-separated list of fields.'
            'Eg. "artist, title")', patterns, row)
        if ok:
            self.listbox.clearSelection()
            self.listbox.addItem(text)
            self.listbox.setCurrentRow(self.listbox.count() - 1)

    def _doubleClicked(self, item):
        self.editItem()

    def editItem(self, row=None):
        if row is None:
            row = self.listbox.currentRow()
        l = self.listbox.item
        patterns = [unicode(l(z).text()) for z in range(self.listbox.count())]
        (text, ok) = QInputDialog().getItem(self, 'Edit', 
            'Enter a sorting option (a comma-separated list of fields.'
            'Eg. "artist, title")', patterns, row)
        if ok:
            item = l(row)
            item.setText(text)
            self.listbox.setItemSelected(item, True)

    def applySettings(self):
        item = self.listbox.item
        options = [unicode(item(row).text())
            for row in xrange(self.listbox.count())]
        self.close()
        self.emit(SIGNAL('options'), options)

class SettingsDialog(QWidget):
    def __init__(self, parent = None, status = None):
        QWidget.__init__(self, parent)
        self.title = 'Tag Sources'
        cparser = PuddleConfig()
        cparser.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        text = cparser.get('tagsources', 'trackpattern', '%track% - %title%')

        sortoptions = cparser.get('tagsources', 'sortoptions', 
            [u'artist, album', u'album, artist'])

        try:
            sortorder = cparser.get('tagsources', 'sortorder', 0)
        except ValueError:
            sortorder = 0
        
        albumformat = cparser.get('tagsources', 'albumpattern',
            u'%artist% - %album% $if(%__numtracks%, [%__numtracks%], "")')
        artoptions = cparser.get('tagsource', 'artoptions',
            ['Replace existing album art.', 'Append to existing album art.',
                "Leave artwork unchanged."])

        saveart = cparser.get('tagsources', 'saveart', False)
        coverdir = cparser.get('tagsources', 'coverdir', False)
        
        label = QLabel('&Display format for individual tracks.')
        self._text = QLineEdit(text)
        label.setBuddy(self._text)
        
        albumlabel = QLabel('Display format for &retrieved albums')
        self._albumdisp = QLineEdit(albumformat)
        albumlabel.setBuddy(self._albumdisp)

        sortlabel = QLabel('Sort retrieved albums using order:')
        self._sortoptions = QComboBox()
        self._sortoptions.addItems(sortoptions)
        sortlabel.setBuddy(self._sortoptions)
        editoptions = QPushButton('&Edit')
        self.connect(editoptions, SIGNAL('clicked()'), self._editOptions)

        self._savecover = QCheckBox('Save album art.')
        
        coverlabel = QLabel("&Directory to save retrieved album art "
            "(it will be created if it doesn't exist)")
        self._coverdir = QLineEdit(tagsources.COVERDIR)
        coverlabel.setBuddy(self._coverdir)
        
        self.connect(self._savecover, SIGNAL('stateChanged(int)'),
            lambda state: self._coverdir.setEnabled(bool(state)))
        
        vbox = QVBoxLayout()
        vbox.addWidget(label)
        vbox.addWidget(self._text)
        
        vbox.addWidget(albumlabel)
        vbox.addWidget(self._albumdisp)
        
        #vbox.addWidget(self._savecover)
        #vbox.addWidget(coverlabel)
        #vbox.addWidget(self._coverdir)

        vbox.addWidget(sortlabel)
        sortbox = QHBoxLayout()
        sortbox.addWidget(self._sortoptions, 1)
        sortbox.addWidget(editoptions)
        vbox.addLayout(sortbox)

        vbox.addStretch()
        self.setLayout(vbox)

    def applySettings(self, control):
        text = unicode(self._text.text())
        control.listbox.trackPattern = text
        coverdir = unicode(self._coverdir.text())
        
        albumdisp = unicode(self._albumdisp.text())
        control.listbox.albumPattern = albumdisp
        
        savecover = bool(self._savecover.checkState())
        coverdir = unicode(self._coverdir.text())
        
        tagsources.set_coverdir(coverdir)
        tagsources.set_savecovers(savecover)
        
        sort_combo = self._sortoptions
        sort_options_text = [unicode(sort_combo.itemText(i)) for i in 
            range(sort_combo.count())]
        sort_options = split_strip(sort_options_text)
        control.listbox.setSortOptions(sort_options)

        control.listbox.sort(sort_options[sort_combo.currentIndex()])

        cparser = PuddleConfig()
        cparser.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        cparser.set('tagsources', 'trackpattern', text)
        cparser.set('tagsources', 'coverdir', coverdir)
        cparser.set('tagsources', 'albumpattern', albumdisp)
        cparser.set('tagsources', 'savecover', savecover)
        cparser.set('tagsources', 'coverdir', coverdir)
        cparser.set('tagsources', 'sortoptions', sort_options_text)
    
    def _editOptions(self):
        text = self._sortoptions.itemText
        win = SortOptionEditor([text(i) for i in 
            range(self._sortoptions.count())], self)
        self.connect(win, SIGNAL('options'), self._setSortOptions)
        win.setModal(True)
        win.show()
    
    def _setSortOptions(self, items):
        current = self._sortoptions.currentText()
        self._sortoptions.clear()
        self._sortoptions.addItems(items)
        index = self._sortoptions.findText(current)
        if index == -1:
            index = 0
        self._sortoptions.setCurrentIndex(index)

class MainWin(QWidget):
    def __init__(self, status, parent = None):
        QWidget.__init__(self, parent)
        self.settingsdialog = SettingsDialog
        self.emits = ['writepreview', 'setpreview', 'clearpreview',
                      'logappend']
        self.setWindowTitle("Tag Sources")
        self._status = status
        if allmusic:
            tagsources = [mbrainz, freedb, amazon, allmusic]
        else:
            tagsources = [mbrainz, freedb, amazon]
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
        self._prefbutton = preferences

        self._searchparams = QLineEdit()
        self._tooltip = "Enter search parameters here. If empty, the selected files are used. <ul><li><b>artist;album</b> searches for a specific album/artist combination.</li> <li>For multiple artist/album combinations separate them with the '|' character. eg. <b>Amy Winehouse;Back To Black|Outkast;Atliens</b>.</li> <li>To list the albums by an artist leave off the album part, but keep the semicolon (eg. <b>Ratatat;</b>). For a album only leave the artist part as in <b>;Resurrection.</li></ul>"
        self._searchparams.setToolTip(self._tooltip)

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
        tooltip = 'Enter a comma seperated list of fields to write. <br /><br />Eg. <b>artist, album, title</b> will only write the artist, album and title fields of the retrieved tags. <br /><br />If you want to exclude some fields, but write all others start the list the tilde (~) character. Eg <b>~composer, __image</b> will write all fields but the composer and __image fields.'
        self._taglist.setToolTip(tooltip)
        self.connect(self._taglist, SIGNAL('tagschanged'), self._changeTags)
        self.connect(self.listbox, SIGNAL('statusChanged'), self.label.setText)
        self.connect(status_obj, SIGNAL('statusChanged'), self.label.setText)
        self.connect(self.listbox, SIGNAL('itemSelectionChanged()'),
                        self._enableWrite)
        self.connect(self.listbox, SIGNAL('exactMatches'),
                        self._enableWrite)
        self.connect(self.listbox, SIGNAL('preview'),
                        lambda tags: self.emit(SIGNAL('setpreview'), tags))
        self.connect(status_obj, SIGNAL('logappend'),
                        lambda text: self.emit(SIGNAL('logappend'), text))
        
        infolabel = QLabel()
        self.connect(self.listbox, SIGNAL('infoChanged'), infolabel.setText)
        
        hbox = QHBoxLayout()
        hbox.addWidget(self._searchparams, 1)
        hbox.addWidget(self.getinfo, 0)

        vbox = QVBoxLayout()
        vbox.addLayout(sourcebox)
        vbox.addLayout(hbox)
        vbox.addWidget(self.label)
        vbox.addWidget(self.listbox, 1)
        hbox = QHBoxLayout()
        hbox.addWidget(infolabel, 1)
        hbox.addStretch()
        hbox.addWidget(self._writebutton)
        hbox.addWidget(clear)
        vbox.addLayout(hbox)

        vbox.addWidget(self._taglist)

        self.setLayout(vbox)
        self._changeSource(0)
        
        self.receives = [('previewModeChanged', self._writebutton.setEnabled)]

    def _clear(self):
        self.emit(SIGNAL('clearpreview'))
        self._writebutton.setEnabled(False)

    def _changeSource(self, index):
        self._tagsource = self._tagsources[index]
        if hasattr(self._tagsource, 'tooltip'):
            self._searchparams.setToolTip(self._tagsource.tooltip)
        else:
            self._searchparams.setToolTip(self._tooltip)
        self.listbox.tagSource = self._tagsource
        if hasattr(self._tagsource, 'preferences'):
            self._config = self._tagsource.preferences
        else:
            self._config = self._configs[index]
        if not self._config:
            self._prefbutton.hide()
        else:
            self._prefbutton.show()
        self._lastindex = index
        self._taglist.setTags(self._tagstowrite[index])

    def _changeTags(self, tags):
        self.listbox.tagsToWrite = tags
        self.listbox.reEmitTracks()
        self._tagstowrite[self._lastindex] = tags

    def _enableWrite(self, value = None):
        self._writebutton.setEnabled(True)

    def _write(self):
        self.emit(SIGNAL('writepreview'))
        self.label.setText("<b>Tags were written.</b>")

    def closeEvent(self, e):
        self._clear()

    def getInfo(self):
        tags = self._status['selectedfiles']
        self.label.setText('Retrieving album info.')
        text = None
        if self._searchparams.text():
            text = unicode(self._searchparams.text())
        elif not tags:
            self.label.setText('<b>Select some files or enter search paramaters.</b>')
            return

        def retrieve():
            try:
                if text:
                    return self._tagsource.keyword_search(text)
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
        if hasattr(config, 'connect'):
            win = config(parent=self)
        else:
            win = SourcePrefs(self._tagsource.name, config, self)
        win.setModal(True)
        self.connect(win, SIGNAL('tagsourceprefs'), self._tagsource.applyPrefs)
        win.show()

    def setInfo(self, retval):
        self.getinfo.setEnabled(True)
        if isinstance(retval, basestring):
            self.label.setText(retval)
        else:
            self.listbox.setReleases(retval)
            if retval:
                self.label.setText(u'Searching complete.')
            else:
                self.label.setText(u'No matching albums were found.')
            self.listbox.emit(SIGNAL('infoChanged'), '')

    def loadSettings(self):
        settings = PuddleConfig()
        settings.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        source = settings.get('tagsources', 'lastsource', 'Musicbrainz')
        self._tagstowrite = [settings.get('tagsourcetags', name , []) for
                                name in self._sourcenames]
        index = self.sourcelist.findText(source)
        self.sourcelist.setCurrentIndex(index)
        self._taglist.setTags(self._tagstowrite[index])
        df = settings.get('tagsources', 'trackpattern', u'%track% - %title%')
        self.listbox.trackPattern = df

        albumformat = settings.get('tagsources', 'albumpattern', 
            u'%artist% - %album%$if(%__numtracks%, [%__numtracks%], "")')
        self.listbox.albumPattern = albumformat

        sort_options = settings.get('tagsources', 'sortoptions', 
            [u'artist, album', u'album, artist'])
        sort_options = split_strip(sort_options)
        self.listbox.setSortOptions(sort_options)

        sortindex = settings.get('tagsources', 'lastsort', 0)
        self.listbox.sort(sort_options[sortindex])


    def saveSettings(self):
        settings = PuddleConfig()
        settings.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        settings.set('tagsources', 'lastsource', self.sourcelist.currentText())
        for i, name in enumerate(self._sourcenames):
            settings.set('tagsourcetags', name , self._tagstowrite[i])
        settings.set('tagsources', 'lastsort', self.listbox.lastSortIndex)

control = ('Tag Sources', MainWin, RIGHTDOCK, False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    status = {}
    status['selectedfiles'] = exampletags.tags
    win = MainWin(status)
    win.show()
    app.exec_()