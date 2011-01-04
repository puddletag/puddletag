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
import sys, pdb, os, traceback
from puddleobjects import (unique, OKCancel, PuddleThread, PuddleConfig, 
    winsettings, ListBox, ListButtons, OKCancel, create_buddy)
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from collections import defaultdict
from puddlestuff.tagsources import (RetrievalError, status_obj, write_log, 
    tagsources, set_useragent, mp3tag)
from puddlestuff.constants import TEXT, COMBO, CHECKBOX, RIGHTDOCK, SAVEDIR
pyqtRemoveInputHook()
from findfunc import replacevars, getfunc
from functools import partial
from copy import copy, deepcopy
from puddlestuff.util import to_string, split_by_tag
from releasewidget import ReleaseWidget
import puddlestuff.audioinfo as audioinfo

TAGSOURCE_CONFIG = os.path.join(SAVEDIR, 'tagsources.conf')
MTAG_SOURCE_DIR = os.path.join(SAVEDIR, 'mp3tag_sources')

tr = lambda s: unicode(QApplication.translate('WebDB', s))

def load_mp3tag_sources(dirpath=MTAG_SOURCE_DIR):
    import glob
    files = glob.glob(os.path.join(dirpath, '*.src'))
    classes = []
    for f in files:
        try:
            idents, search, album = mp3tag.open_script(f)
            classes.append(mp3tag.Mp3TagSource(idents, search, album))
        except:
            print tr("Couldn't load Mp3tag Tag Source %s") % f
            traceback.print_exc()
            continue
    return classes

def display_tag(tag):
    """Used to display tags in in a human parseable format."""
    if not tag:
        return tr("<b>Error in pattern</b>")
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
    return replacevars(getfunc(pattern, tags), audioinfo.stringtags(tags))

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
        label.setText(QApplication.translate("Defaults", '&Fields'))
        self._text = QLineEdit(u', '.join(tags))
        label.setBuddy(self._text)

        layout = QHBoxLayout()
        layout.setMargin(0)
        layout.addWidget(label, 0)
        layout.addWidget(self._text, 1)

        self.connect(self._text, SIGNAL('textChanged(QString)'), self.emitTags)

        self.setLayout(layout)

    def tags(self, text=None):
        if not text:
            return filter(None, [z.strip() for z in
                unicode(self._text.text()).split(u',')])
        else:
            return filter(None, [z.strip() for z in unicode(text).split(u',')])

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
        self.setWindowTitle(tr('Configure: %s') % title)
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
        hbox.addWidget(self.listbox, 1)

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
        (text, ok) = QInputDialog().getItem(self, tr('Add sort option'),
            tr('Enter a sorting option (a comma-separated list of fields. '
                'Eg. "artist, title")'), patterns, row)
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
        (text, ok) = QInputDialog().getItem(self,
            tr('Edit sort option'),
            tr('Enter a sorting option (a comma-separated list of fields. '
            'Eg. "artist, title")'), patterns, row)
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

        label = QLabel(tr('&Display format for individual tracks.'))
        self._text = QLineEdit()
        label.setBuddy(self._text)
        
        albumlabel = QLabel(tr('Display format for &retrieved albums'))
        self._albumdisp = QLineEdit()
        albumlabel.setBuddy(self._albumdisp)

        sortlabel = QLabel(tr('Sort retrieved albums using order:'))
        self._sortoptions = QComboBox()
        sortlabel.setBuddy(self._sortoptions)
        editoptions = QPushButton(QApplication.translate("Defaults", '&Edit'))
        self.connect(editoptions, SIGNAL('clicked()'), self._editOptions)
        
        ua_label = QLabel(tr('User-Agent to use for screen scraping.'))
        self._ua = QTextEdit()

        self.jfdi = QCheckBox(QApplication.translate('Profile Editor',
            'Brute force unmatched files.'))
        self.jfdi.setToolTip(QApplication.translate('Profile Editor',"<p>If a proper match isn't found for a file, the files will get sorted by filename, the retrieved tag sources by filename and corresponding (unmatched) tracks will matched.</p>"))
        self.matchFields = QLineEdit(u'artist, title')
        self.matchFields.setToolTip(QApplication.translate('Profile Editor','<p>The fields listed here will be used in determining whether a track matches the retrieved track. Each field will be compared using a fuzzy matching algorithm. If the resulting average match percentage is greater than the "Minimum Percentage" it\'ll be considered to match.</p>'))

        self.albumBound = QSpinBox()
        self.albumBound.setToolTip(QApplication.translate('Profile Editor',"<p>The artist and album fields will be used in determining whether an album matches the retrieved one. Each field will be compared using a fuzzy matching algorithm. If the resulting average match percentage is greater or equal than what you specify here it'll be considered to match.</p>"))
        self.albumBound.setRange(0,100)
        self.albumBound.setValue(70)
        
        self.trackBound = QSpinBox()
        self.trackBound.setRange(0,100)
        self.trackBound.setValue(80)
        
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

        vbox.addWidget(ua_label)
        vbox.addWidget(self._ua)

        frame = QGroupBox(QApplication.translate(
            'WebDB', 'Automatic retrieval options'))

        auto_box = QVBoxLayout()
        frame.setLayout(auto_box)

        auto_box.addLayout(create_buddy(QApplication.translate('Profile Editor',
                'Minimum &percentage required for album matches.'),
            self.albumBound))
        auto_box.addLayout(create_buddy(QApplication.translate('Profile Editor',
                'Match tracks using &fields: '), self.matchFields))
        auto_box.addLayout(create_buddy(QApplication.translate(
                'Profile Editor','Minimum percentage required for track match.'),
            self.trackBound))
        auto_box.addWidget(self.jfdi)

        vbox.addWidget(frame)

        vbox.addStretch()
        self.setLayout(vbox)
        self.loadSettings()

    def applySettings(self, control):
        listbox = control.listbox
        text = unicode(self._text.text())
        listbox.trackPattern = text

        albumdisp = unicode(self._albumdisp.text())
        listbox.albumPattern = albumdisp

        sort_combo = self._sortoptions
        sort_options_text = [unicode(sort_combo.itemText(i)) for i in 
            range(sort_combo.count())]
        sort_options = split_strip(sort_options_text)
        listbox.setSortOptions(sort_options)

        listbox.sort(sort_options[sort_combo.currentIndex()])
        
        useragent = unicode(self._ua.toPlainText())
        set_useragent(useragent)

        listbox.jfdi = self.jfdi.isChecked()
        listbox.matchFields = [z.strip() for z in
            unicode(self.matchFields.text()).split(u',')]
        listbox.albumBound = self.albumBound.value() / 100.0
        listbox.trackBound = self.trackBound.value() / 100.0
        
        cparser = PuddleConfig(os.path.join(SAVEDIR, 'tagsources.conf'))
        set_value = lambda s,v: cparser.set('tagsources', s, v)
        set_value('trackpattern', text)
        set_value('albumpattern', albumdisp)
        set_value('sortoptions', sort_options_text)
        set_value('useragent', useragent)
        set_value('album_bound', self.albumBound.value())
        set_value('track_bound', self.trackBound.value())
        set_value('jfdi', listbox.jfdi)
        set_value('match_fields', listbox.matchFields)

    def loadSettings(self):
        cparser = PuddleConfig(os.path.join(SAVEDIR, 'tagsources.conf'))

        trackpattern = cparser.get('tagsources', 'trackpattern',
            '%track% - %title%')

        self._text.setText(trackpattern)

        sortoptions = cparser.get('tagsources', 'sortoptions',
            [u'artist, album', u'album, artist'])
        self._sortoptions.clear()
        self._sortoptions.addItems(sortoptions)

        albumformat = cparser.get('tagsources', 'albumpattern',
            u'%artist% - %album% $if(%__numtracks%, [%__numtracks%], "")')
        self._albumdisp.setText(albumformat)

        self._ua.setText(cparser.get('tagsources', 'useragent', ''))

        self.albumBound.setValue(
            cparser.get('tagsources', 'album_bound', 70, True))
        self.trackBound.setValue(
            cparser.get('tagsources', 'track_bound', 80, True))
        self.jfdi.setChecked(
            bool(cparser.get('tagsources', 'jfdi', True, True)))

        fields = cparser.get('tagsources', 'match_fields', ['artist', 'title'])
        fields = u', '.join(z.strip() for z in fields)
        self.matchFields.setText(fields)
    
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

def load_source_prefs(name, preferences):
    cparser = PuddleConfig(TAGSOURCE_CONFIG)
    return [cparser.get(name, option[0], option[2]) if 
        option[1] != COMBO else 
        cparser.get(name, option[0], option[2][1]) for 
        option in preferences]

class MainWin(QWidget):
    def __init__(self, status, parent = None):
        QWidget.__init__(self, parent)
        self.settingsdialog = SettingsDialog
        self.emits = ['writepreview', 'setpreview', 'clearpreview',
            'enable_preview_mode', 'logappend', 'disable_preview_mode']
        self.receives = []
        self.setWindowTitle("Tag Sources")
        self.mapping = audioinfo.mapping
        self._status = status
        self._tagsources = [z() for z in tagsources]
        self._tagsources.extend(load_mp3tag_sources())
        [z.applyPrefs(load_source_prefs(z.name, z.preferences)) 
            for z in self._tagsources if
            hasattr(z, 'preferences') and not isinstance(z, QWidget)]
        status['initialized_tagsources'] = self._tagsources
        self._configs = [z.preferences if hasattr(z, 'preferences') else None
            for z in self._tagsources]
        self._tagsource = self._tagsources[0]
        self._tagstowrite = [[] for z in self._tagsources]
        self._sourcenames = [z.name for z in self._tagsources]
        self._lastindex = 0

        self.sourcelist = QComboBox()
        self.sourcelist.addItems(self._sourcenames)
        self.connect(self.sourcelist, SIGNAL('currentIndexChanged (int)'),
                        self._changeSource)
        sourcelabel = QLabel(tr('Sour&ce: '))
        sourcelabel.setBuddy(self.sourcelist)

        preferences = QToolButton()
        preferences.setIcon(QIcon(':/preferences.png'))
        preferences.setToolTip(tr('Configure'))
        self.connect(preferences, SIGNAL('clicked()'), self.configure)

        sourcebox = QHBoxLayout()
        sourcebox.addWidget(sourcelabel)
        sourcebox.addWidget(self.sourcelist, 1)
        sourcebox.addWidget(preferences)
        self._prefbutton = preferences

        self._searchparams = QLineEdit()
        self._tooltip = tr("Enter search parameters here. If empty, the selected files are used. <ul><li><b>artist;album</b> searches for a specific album/artist combination.</li><li>To list the albums by an artist leave off the album part, but keep the semicolon (eg. <b>Ratatat;</b>). For a album only leave the artist part as in <b>;Resurrection.</li></ul>")
        self._searchparams.setToolTip(self._tooltip)

        self.getinfo = QPushButton(tr("&Search"))
        self.getinfo.setDefault(True)
        self.getinfo.setAutoDefault(True)
        self.connect(self._searchparams, SIGNAL('returnPressed()'), self.getInfo)
        self.connect(self.getinfo , SIGNAL("clicked()"), self.getInfo)

        self._writebutton = QPushButton(tr('&Write'))
        clear = QPushButton(QApplication.translate("Previews", "Clea&r preview"))

        self.connect(self._writebutton, SIGNAL("clicked()"), self._write)
        self.connect(clear, SIGNAL("clicked()"), self._clear)

        self.label = QLabel(tr("Select files and click on Search to retrieve "
            "metadata."))

        self.listbox = ReleaseWidget(status, self._tagsource)
        self._existing = QCheckBox(QApplication.translate("WebDB",
            'Update empty fields only.'))
        self._auto = QCheckBox(QApplication.translate("WebDB",
            'Automatically retrieve matches.'))

        self._taglist = TagListWidget()
        tooltip = tr('Enter a comma seperated list of fields to write. <br /><br />Eg. <b>artist, album, title</b> will only write the artist, album and title fields of the retrieved tags. <br /><br />If you want to exclude some fields, but write all others start the list the tilde (~) character. Eg <b>~composer, __image</b> will write all fields but the composer and __image fields.')
        self._taglist.setToolTip(tooltip)
        self.connect(self._taglist, SIGNAL('tagschanged'), self._changeTags)
        self.connect(self.listbox, SIGNAL('statusChanged'), self.label.setText)
        #self.connect(self.listbox, SIGNAL('retrieving'), partial(self.setEnabled, False))
        #self.connect(self.listbox, SIGNAL('retrievalDone'), partial(self.setEnabled, True))
        self.connect(status_obj, SIGNAL('statusChanged'), self.label.setText)
        
        self.connect(self.listbox, SIGNAL('preview'), self.emit_preview)
        self.connect(self.listbox, SIGNAL('exact'), self.emitExact)
        self.connect(status_obj, SIGNAL('logappend'), SIGNAL('logappend'))
        
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
        vbox.addWidget(self._existing)
        vbox.addWidget(self._auto)
        self.setLayout(vbox)
        self._changeSource(0)
        
    def _applyPrefs(self, prefs):
        self._tagsource.applyPrefs(prefs)
        cparser = PuddleConfig(os.path.join(SAVEDIR, 'tagsources.conf'))
        name = self._tagsource.name
        for section, value in zip(self._tagsource.preferences, prefs):
            cparser.set(name, section[0], value)

    def _clear(self):
        self.emit(SIGNAL('disable_preview_mode'))

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
        if self._tagsource.name in self.mapping:
            self.listbox.setMapping(self.mapping[self._tagsource.name])
        else:
            self.listbox.setMapping({})
        
        if hasattr(self._tagsource, 'keyword_search'):
            self._searchparams.setEnabled(True)
        else:
            self._searchparams.setEnabled(False)

    def _changeTags(self, tags):
        self.listbox.tagsToWrite = tags
        self.listbox.reEmitTracks()
        self._tagstowrite[self._lastindex] = tags

    def _write(self):
        self.emit(SIGNAL('writepreview'))
        self.label.setText(tr("<b>Tags were written.</b>"))

    def closeEvent(self, e):
        self._clear()
    
    def emit_preview(self, tags):
        if not self._existing.isChecked():
            self.emit(SIGNAL('enable_preview_mode'))
            self.emit(SIGNAL('setpreview'), tags)
        else:
            files = self._status['selectedfiles']
            previews = []
            for f, r in zip(files, tags):
                temp = {}
                for field in r:
                    if field not in f:
                        temp[field] = r[field]
                previews.append(temp)
            self.emit(SIGNAL('enable_preview_mode'))
            self.emit(SIGNAL('setpreview'), previews)

    def emitExact(self, d):
        if not self._existing.isChecked():
            self.emit(SIGNAL('enable_preview_mode'))
            self.emit(SIGNAL('setpreview'), d)
        else:
            previews = []
            for f, r in d.items():
                temp = {}
                for field in r:
                    if field not in f:
                        temp[field] = r[field]
                previews.append(temp)
            pdb.set_trace()
            self.emit(SIGNAL('enable_preview_mode'))
            self.emit(SIGNAL('setpreview'), previews)

    def getInfo(self):
        files = self._status['selectedfiles']
        if self._tagsource.group_by:
            group = split_by_tag(files, *self._tagsource.group_by)
        self.label.setText(tr('Retrieving album info.'))
        text = None
        if self._searchparams.text() and self._searchparams.isEnabled():
            text = unicode(self._searchparams.text())
        elif not files:
            self.label.setText(tr('<b>Select some files or enter search paramaters.</b>'))
            return

        def search():
            try:
                ret = []
                if text:
                    return self._tagsource.keyword_search(text), None
                else:
                    if self._tagsource.group_by:
                        for primary in group:
                            ret.extend(self._tagsource.search(
                                primary, group[primary]))
                        return ret, files
                    else:
                        return self._tagsource.search(files), files
            except RetrievalError, e:
                return 'An error occured: %s' % unicode(e)
        self.getinfo.setEnabled(False)
        self._t = PuddleThread(search)
        self.connect(self._t, SIGNAL('threadfinished'), self.setInfo)
        self._t.start()

    def configure(self):
        config = self._config
        if config is None:
            return
        if hasattr(config, 'connect'):
            win = config(parent=self)
        else:
            defaults = load_source_prefs(self._tagsource.name, config)
            prefs = deepcopy(config)
            for pref, value in zip(prefs, defaults):
                if pref[1] != COMBO:
                    pref[2] = value
                else:
                    pref[2][1] = value
            win = SourcePrefs(self._tagsource.name, prefs, self)
        win.setModal(True)
        self.connect(win, SIGNAL('tagsourceprefs'), self._applyPrefs)
        win.show()

    def setInfo(self, retval):
        self.getinfo.setEnabled(True)
        if isinstance(retval, basestring):
            self.label.setText(retval)
        else:
            releases, files = retval
            if releases:
                self.label.setText(tr('Searching complete.'))
            else:
                self.label.setText(tr('No matching albums were found.'))
            if files and self._auto.isChecked():
                self.listbox.setReleases(releases, files)
            else:
                self.listbox.setReleases(releases)
            self.listbox.emit(SIGNAL('infoChanged'), '')

    def loadSettings(self):
        settings = PuddleConfig(os.path.join(SAVEDIR, 'tagsources.conf'))
        get = lambda s, k, i=False: settings.get('tagsources', s, k, i)
        
        source = get('lastsource', 'Musicbrainz')
        self._tagstowrite = [settings.get('tagsourcetags', name , []) for
                                name in self._sourcenames]
        index = self.sourcelist.findText(source)
        self.sourcelist.setCurrentIndex(index)
        self._taglist.setTags(self._tagstowrite[index])
        df = get('trackpattern', u'%track% - %title%')
        self.listbox.trackPattern = df

        albumformat = get('albumpattern',
            u'%artist% - %album%$if(%__numtracks%, [%__numtracks%], "")')
        self.listbox.albumPattern = albumformat

        sort_options = get('sortoptions',
            [u'artist, album', u'album, artist'])
        sort_options = split_strip(sort_options)
        self.listbox.setSortOptions(sort_options)

        sortindex = get('lastsort', 0)
        self.listbox.sort(sort_options[sortindex])
        
        filepath = os.path.join(SAVEDIR, 'mappings')
        self.setMapping(audioinfo.loadmapping(filepath))
        
        useragent = get('useragent', '')
        if useragent:
            set_useragent(useragent)
        
        checkstate = get('existing', False)
        self._existing.setChecked(checkstate)

        checkstate = get('autoretrieve', False)
        self._auto.setChecked(checkstate)

        self.listbox.albumBound = get('album_bound', 70, True) / 100.0
        self.listbox.trackBound = get('track_bound', 80, True) / 100.0
        self.listbox.jfdi = bool(get('jfdi', True, True))
        self.listbox.matchFields = get('match_fields', ['artist' 'title'])

    def saveSettings(self):
        settings = PuddleConfig()
        settings.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        settings.set('tagsources', 'lastsource', self.sourcelist.currentText())
        for i, name in enumerate(self._sourcenames):
            settings.set('tagsourcetags', name , self._tagstowrite[i])
        settings.set('tagsources', 'lastsort', self.listbox.lastSortIndex)
        settings.set('tagsources', 'existing', self._existing.isChecked())
        settings.set('tagsources', 'autoretrieve', self._auto.isChecked())
    
    def setMapping(self, mapping):
        self.mapping = mapping
        if self._tagsource.name in mapping:
            self.listbox.setMapping(mapping[self._tagsource.name])
        else:
            self.listbox.setMapping({})

control = ('Tag Sources', MainWin, RIGHTDOCK, False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    status = {}
    status['selectedfiles'] = exampletags.tags
    win = MainWin(status)
    win.show()
    app.exec_()