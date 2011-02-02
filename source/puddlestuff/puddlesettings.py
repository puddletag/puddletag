#!/usr/bin/env python
# -*- coding: utf-8 -*-
#puddlesettings.py

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


"""In this module, all the dialogs for configuring puddletag are
stored. These are accessed via the Preferences window.

The MainWin class is the important class since it creates,
the dialogs in a stacked widget and calls their methods as needed.

Each dialog must have in its __init__ method an argument called 'cenwid'.
cenwid is puddletag's main window found in puddletag.MainWin.
If cenwid is passed, then the dialog should read all it's values,
apply them (if needed) and return(close). This is done when puddletag starts.

In addition, each dialog should have a saveSettings functions, which
is called when settings pertinent to that dialog need to be saved.

It is not required, that each dialog should also have
an applySettings(self, cenwid) method, which is called when
settings need to be applied while puddletag is running.
"""

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys, resource, os
from copy import copy
from puddleobjects import (ListButtons, OKCancel, HeaderSetting,
    ListBox, PuddleConfig, winsettings, get_languages, create_buddy)
from shortcutsettings import ActionEditorDialog
from puddlestuff.pluginloader import PluginConfig
import pdb
import audioinfo.util
import genres, confirmations
from action_shortcuts import ShortcutEditor
from copy import deepcopy
from puddlestuff.translations import translate
from puddlestuff.constants import TRANSDIR

class SettingsError(Exception):
    pass

def load_gen_settings(setlist, extras=False):
    settings = PuddleConfig()
    settings.filename = os.path.join(settings.savedir, 'gensettings')
    ret = []
    for setting in setlist:
        desc = setting[0]
        default = setting[1]
        ret.append([desc, settings.get(desc, 'value', default)])
    return ret

def save_gen_settings(setlist):
    settings = PuddleConfig()
    settings.filename = os.path.join(settings.savedir, 'gensettings')
    for desc, value in setlist.items():
        settings.set(desc, 'value', value)

class SettingsCheckBox(QCheckBox):
    def __init__(self, default=None, text=None, parent=None):
        QCheckBox.__init__(self, QApplication.translate("GenSettings", text), parent)

        self.settingValue = default
        self._text = text

    def _value(self):
        if self.checkState() == Qt.Checked:
            return self._text, True
        else:
            return self._text, False

    def _setValue(self, value):
        if value:
            self.setCheckState(Qt.Checked)
        else:
            self.setCheckState(Qt.Unchecked)

    settingValue = property(_value, _setValue)

class SettingsLineEdit(QWidget):
    def __init__(self, desc, default, parent=None):
        QWidget.__init__(self, parent)
        vbox = QVBoxLayout()
        vbox.setMargin(0)
        self._text = QLineEdit(default)
        label = QLabel(QApplication.translate("GenSettings", desc))
        self._desc = desc
        label.setBuddy(self._text)
        vbox.addWidget(label)
        vbox.addWidget(self._text)
        self.setLayout(vbox)

    def _value(self):
        return self._desc, unicode(self._text.text())

    def _setValue(self, value):
        self._text.setText(self._desc, text)

    settingValue = property(_value, _setValue)

class GeneralSettings(QWidget):
    def __init__(self, controls, parent = None):
        QWidget.__init__(self, parent)
        settings = []
        for control in controls:
            if hasattr(control, 'gensettings'):
                settings.extend(load_gen_settings(control.gensettings, True))
        self._controls = []

        def create_control(desc, val):
            if isinstance(val, bool):
                return SettingsCheckBox(val, desc)
            elif isinstance(val, basestring):
                return SettingsLineEdit(desc, val)

        vbox = QVBoxLayout()
        for desc, val in settings:
            widget = create_control(desc, val)
            vbox.addWidget(widget)
            self._controls.append(widget)

        edit_sort_options = QPushButton(
            translate("GenSettings", '&Edit sort options'))

        self._lang_combo = QComboBox()
        self._lang_combo.addItems([translate('GenSettings', '<Autodetect>'),
            translate('GenSettings', 'Default')])
        self._lang_combo.setCurrentIndex(0)

        lang = PuddleConfig().get('main', 'lang', u'auto')
        self._lang_combo.addItems(list(get_languages([TRANSDIR])))

        if lang != u'auto':
            i = self._lang_combo.findText(lang, Qt.MatchFixedString)
            if i > 0:
                self._lang_combo.setCurrentIndex(i)
        
        self.connect(edit_sort_options, SIGNAL('clicked()'), 
            self.editSortOptions)

        hbox = QHBoxLayout()
        hbox.addWidget(edit_sort_options)
        hbox.addStretch()
        
        vbox.addLayout(hbox)
        if self._lang_combo.count() > 2:
            vbox.addLayout(create_buddy(
                translate('GenSettings', 'Language (Requires a restart)'),
                self._lang_combo))
        else:
            self._lang_combo.setCurrentIndex(0)
        vbox.addStretch()
        self.setLayout(vbox)
        
    def editSortOptions(self):
        cparser = PuddleConfig()
        options = cparser.get('table', 'sortoptions', 
            ['__filename,track,__dirpath','track, album', 
            '__filename,album,__dirpath'])

        from puddlestuff.webdb import SortOptionEditor
        win = SortOptionEditor(options, self)
        self.connect(win, SIGNAL('options'), self.applySortOptions)
        win.show()
    
    def applySortOptions(self, options):
        import puddlestuff.mainwin.previews
        puddlestuff.mainwin.previews.set_sort_options(options)
        cparser = PuddleConfig()
        cparser.set('table', 'sortoptions', options)

    def applySettings(self, controls):

        cparser = PuddleConfig()
        index = self._lang_combo.currentIndex()
        if index > 1:
            cparser.set('main', 'lang', unicode(self._lang_combo.currentText()))
        elif index == 0:
            cparser.set('main', 'lang', u'auto')
        elif index == 1:
            cparser.set('main', 'lang', u'default')
        
        vals =  dict([c.settingValue for c in self._controls])
        for c in controls:
            if hasattr(c, 'applyGenSettings'):
                c.applyGenSettings(vals)
        save_gen_settings(vals)

class Playlist(QWidget):
    def __init__(self, parent = None):
        QWidget.__init__(self, parent)

        def inttocheck(value):
            if value:
                return Qt.Checked
            return Qt.Unchecked

        cparser = PuddleConfig()

        self.extpattern = QLineEdit()
        self.extpattern.setText(cparser.load('playlist', 'extpattern','%artist% - %title%'))
        hbox = QHBoxLayout()
        hbox.addSpacing(10)
        hbox.addWidget(self.extpattern)

        self.extinfo = QCheckBox(QApplication.translate("Playlist Settings", '&Write extended info'), self)
        self.connect(self.extinfo, SIGNAL('stateChanged(int)'), self.extpattern.setEnabled)
        self.extinfo.setCheckState(inttocheck(cparser.load('playlist', 'extinfo',1, True)))
        self.extpattern.setEnabled(self.extinfo.checkState())

        self.reldir = QCheckBox(QApplication.translate("Playlist Settings", 'Entries &relative to working directory'))
        self.reldir.setCheckState(inttocheck(cparser.load('playlist', 'reldir',0, True)))


        self.filename = QLineEdit()
        self.filename.setText(cparser.load('playlist', 'filepattern','puddletag.m3u'))
        label = QLabel(QApplication.translate("Playlist Settings", '&Filename pattern.'))
        label.setBuddy(self.filename)

        vbox = QVBoxLayout()
        [vbox.addWidget(z) for z in (self.extinfo, self.reldir,
            label, self.filename)]
        vbox.insertLayout(1, hbox)
        vbox.addStretch()
        vbox.insertSpacing(2, 5)
        vbox.insertSpacing(4, 5)
        self.setLayout(vbox)

    def applySettings(self, control=None):
        def checktoint(checkbox):
            if checkbox.checkState() == Qt.Checked:
                return 1
            else:
                return 0
        cparser = PuddleConfig()
        cparser.setSection('playlist', 'extinfo', checktoint(self.extinfo))
        cparser.setSection('playlist', 'extpattern', unicode(self.extpattern.text()))
        cparser.setSection('playlist', 'reldir', checktoint(self.reldir))
        cparser.setSection('playlist', 'filepattern', unicode(self.filename.text()))

class TagMappings(QWidget):
    def __init__(self, parent = None):
        filename = os.path.join(PuddleConfig().savedir, 'mappings')
        self._edited = deepcopy(audioinfo.mapping)
        self._mappings = audioinfo.mapping

        QWidget.__init__(self, parent)
        tooltip = translate("Mapping Settings",
            '''<ul><li>Tag is the format that the mapping applies to.
            One of <b>ID3, APEv2, MP4, or VorbisComment</b>.
            </li><li>Fields will be mapped from Source to Target,
            meaning that if Source is found in a tag, it'll be
            editable in puddletag using Target.</li>
            <li>Eg. For <b>Tag=VorbisComment, Source=organization,
            and Target=publisher</b> means that writing to the publisher
            field for VorbisComments in puddletag will in actuality
            write to the organization field.</li><li>Mappings for
            tag sources are also supported, just use the name of the
            tag source as Tag, eg. <b>Tag=MusicBrainz,
            Source=artist,Target=performer</b>.</li></ul>''')
        
        self._table = QTableWidget()
        self._table.setToolTip(tooltip)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([
            QApplication.translate("Mapping Settings", 'Tag'),
            QApplication.translate("Mapping Settings", 'Source'),
            QApplication.translate("Mapping Settings", 'Target')])
        header = self._table.horizontalHeader()
        header.setVisible(True)
        self._table.verticalHeader().setVisible(False)
        header.setStretchLastSection(True)
        buttons = ListButtons()
        buttons.connectToWidget(self)
        buttons.moveup.setVisible(False)
        buttons.movedown.setVisible(False)
        self.connect(buttons, SIGNAL('duplicate'), self.duplicate)

        hbox = QHBoxLayout()
        hbox.addWidget(self._table, 1)
        hbox.addLayout(buttons, 0)

        self._setMappings(self._mappings)
        label = QLabel(translate("Mapping Settings",
            '<b>A restart is required to apply these settings.</b>'))
        vbox = QVBoxLayout()
        vbox.addLayout(hbox, 1)
        vbox.addWidget(label)
        self.setLayout(vbox)

    def _setMappings(self, mappings):
        self._table.clearContents()
        setItem = self._table.setItem
        self._table.setRowCount(1)
        row = 0
        if 'puddletag' in mappings:
            puddletag = mappings['puddletag']
        else:
            puddletag = {}
        for z, v in mappings.items():
            for source, target in v.items():
                if source in puddletag and z != 'puddletag':
                    continue
                setItem(row, 0, QTableWidgetItem(z))
                setItem(row, 1, QTableWidgetItem(source))
                setItem(row, 2, QTableWidgetItem(target))
                row += 1
                self._table.setRowCount(row + 1)
        self._table.removeRow(self._table.rowCount() -1)
        self._table.resizeColumnsToContents()

    def add(self):
        table = self._table
        row = table.rowCount()
        table.insertRow(row)
        for column, v in enumerate([
            QApplication.translate("Mapping Settings", 'Tag'),
            QApplication.translate("Mapping Settings", 'Source'),
            QApplication.translate("Mapping Settings", 'Target')]):
            table.setItem(row, column, QTableWidgetItem(v))
        item = table.item(row, 0)
        table.setCurrentItem(item)
        table.editItem(item)

    def edit(self):
        self._table.editItem(self._table.currentItem())

    def remove(self):
        self._table.removeRow(self._table.currentRow())

    def applySettings(self, *args):
        text = []
        mappings = {}
        item = self._table.item
        itemtext = lambda row, column: unicode(item(row, column).text())
        for row in range(self._table.rowCount()):
            tag = itemtext(row, 0)
            original = itemtext(row, 1)
            other = itemtext(row, 2)
            text.append((tag, original, other))
            if tag in mappings:
                mappings[tag].update({other: original})
            else:
                mappings[tag] = {other: original}
        self._mappings = mappings
        filename = os.path.join(PuddleConfig().savedir, 'mappings')
        f = open(filename, 'w')
        f.write('\n'.join([','.join(z) for z in text]))
        f.close()

    def duplicate(self):
        table = self._table
        row = table.currentRow()
        if row < 0: return
        item = table.item
        itemtext = lambda column: unicode(item(row, column).text())
        texts = [itemtext(z) for z in range(3)]
        row = table.rowCount()
        table.insertRow(row)
        for column, v in enumerate(texts):
            table.setItem(row, column, QTableWidgetItem(v))
        item = table.item(row, 0)
        table.setCurrentItem(item)
        table.editItem(item)

class Tags(QWidget):
    def __init__(self, parent = None):
        QWidget.__init__(self, parent)
        self._edited = False
        
        self._filespec = QLineEdit()
        speclabel = QLabel(QApplication.translate("Tag Settings", '&Restrict incoming files to (eg. "*.mp3; *.ogg; *.aac")'))
        speclabel.setBuddy(self._filespec)

        v1_options = [QApplication.translate("Tag Settings", 'Remove ID3v1 tag.'),
            QApplication.translate("Tag Settings", "Update the ID3v1 tag's values only if an ID3v1 tag is present."),
            QApplication.translate("Tag Settings", "Create an ID3v1 tag if it's not present. Otherwise update it.")]
        self._v1_combo = QComboBox()
        self._v1_combo.addItems(v1_options)
        
        v1_label = QLabel(QApplication.translate("Tag Settings", 'puddletag writes only &ID3v2 tags. What should be done with the ID3v1 tag?'))
        v1_label.setBuddy(self._v1_combo)
        
        self._apev2 = QCheckBox(QApplication.translate("Tag Settings", 'Write APEv2'))
        
        layout = QVBoxLayout()
        vbox = QVBoxLayout()
        
        layout.addWidget(speclabel)
        layout.addWidget(self._filespec)
        
        vbox.addWidget(v1_label)
        vbox.addWidget(self._v1_combo)
        
        #vbox.addWidget(self._apev2)
        
        vbox.addStretch()
        
        group = QGroupBox('ID3')
        group.setLayout(vbox)

        layout.addWidget(group)
        self.setLayout(layout)

        cparser = PuddleConfig()
        index = cparser.get('id3tags', 'v1_option', 2)
        self._v1_combo.setCurrentIndex(index)
        filespec = u';'.join(cparser.get('table', 'filespec', []))
        self._filespec.setText(filespec)
        
        write_ape = cparser.get('id3tags', 'write_ape', False)
        
        self._apev2.setChecked(write_ape)

    def applySettings(self, control=None):
        cparser = PuddleConfig()
        v1_option = self._v1_combo.currentIndex()
        cparser.set('id3tags', 'v1_option', v1_option)
        audioinfo.id3.v1_option = v1_option

        filespec = unicode(self._filespec.text())
        control.filespec = filespec
        filespec = [z.strip() for z in filespec.split(';')]
        cparser.set('table', 'filespec', filespec)

        cparser.set('id3tags', 'write_ape', False)
        #cparser.set('id3tags', 'write_ape', self._apev2.isChecked())
        audioinfo.set_id3_options(self._apev2.isChecked())

class ListModel(QAbstractListModel):
    def __init__(self, options):
        QAbstractListModel.__init__(self)
        self.options = options

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
            return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            return QVariant(self.headerdata[section])
        return QVariant(int(section + 1))

    def data(self, index, role = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.options)):
            return QVariant()
        if (role == Qt.DisplayRole) or (role == Qt.ToolTipRole):
            try:
                return QVariant(self.options[index.row()][0])
            except IndexError: return QVariant()
        return QVariant()

    def widget(self, row):
        return self.options[row][1]

    def rowCount(self, index = QModelIndex()):
        return len(self.options)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractListModel.flags(self, index))

class SettingsList(QListView):
    """Just want a list that emits a selectionChanged signal, with
    the currently selected row."""
    def __init__(self, parent = None):
        QListView.__init__(self, parent)

    def selectionChanged(self, selected, deselected):
        self.emit(SIGNAL("selectionChanged"), selected.indexes()[0].row())

class StatusWidgetItem(QTableWidgetItem):
    def __init__(self, text, color):
        QTableWidgetItem.__init__(self, text)
        self.setBackground(QBrush(color))
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

class ColorEdit(QWidget):
    def __init__(self, parent = None):
        QWidget.__init__(self, parent)
        cparser = PuddleConfig()
        get_color = lambda key, default: QColor.fromRgb(
            *cparser.get('extendedtags', key, default, True))
        add = get_color('add', [0,255,0])
        edit = get_color('edit', [255,255,0])
        remove = get_color('remove', [255,0,0])

        get_color = lambda key, default: QColor.fromRgb(
            *cparser.get('table', key, default, True))

        preview = get_color('preview_color', [192, 255, 192])
        selection_default = QPalette().color(QPalette.Mid).getRgb()[:-1]
        
        selection = get_color('selected_color', selection_default)
        
        colors = (add, edit, remove, preview, selection)

        label = QLabel(QApplication.translate("Colour Settings",
            '<p>Below are the backgrounds used for various ' \
            'controls in puddletag. <br \>Double click the desired action ' \
            'to change its colour.</p>'))

        self.listbox = QTableWidget(0, 1, self)
        self.listbox.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.listbox.horizontalHeader()
        self.listbox.setSortingEnabled(False)
        header.setVisible(True)
        header.setStretchLastSection (True)
        self.listbox.setHorizontalHeaderLabels(['Action'])
        self.listbox.setRowCount(len(colors))

        titles = [
            (QApplication.translate("Colour Settings", 'Row selected in file-view.'), selection),
            (QApplication.translate("Colour Settings", 'Row colour for files with previews.'), preview),
            (QApplication.translate("Colour Settings", 'Field added in Extended Tags.'), add),
            (QApplication.translate("Colour Settings", 'Field edited in Extended Tags.'), edit),
            (QApplication.translate("Colour Settings", 'Field removed in Extended Tags.'), remove),]

        for i, z in enumerate(titles):
            self.listbox.setItem(i, 0, StatusWidgetItem(*z))

        vbox = QVBoxLayout()
        vbox.addWidget(label)
        vbox.addWidget(self.listbox)
        self.setLayout(vbox)
        self.connect(self.listbox, SIGNAL('cellDoubleClicked(int,int)'), self.edit)

    def edit(self, row, column):
        self._status = (row, self.listbox.item(row, column).background())
        win = QColorDialog(self)
        win.setCurrentColor(self.listbox.item(row, column).background().color())
        self.connect(win, SIGNAL('currentColorChanged(const QColor&)'),
            self.intermediateColor)
        self.connect(win, SIGNAL('rejected()'), self.setColor)
        win.open()

    def setColor(self):
        row = self._status[0]
        self.listbox.item(row, 0).setBackground(self._status[1])

    def intermediateColor(self, color):
        row = self._status[0]
        if color.isValid():
            self.listbox.item(row, 0).setBackground(QBrush(color))

    def applySettings(self, control=None):
        cparser = PuddleConfig()
        x = lambda c: c.getRgb()[:-1]
        colors = [x(self.listbox.item(z,0).background().color())
            for z in range(self.listbox.rowCount())]
        cparser.set('table', 'selected_color', colors[0])
        cparser.set('table', 'preview_color', colors[1])
        cparser.set('extendedtags', 'add', colors[2])
        cparser.set('extendedtags', 'edit', colors[3])
        cparser.set('extendedtags', 'remove', colors[4])

        control.model().selectionBackground = QColor.fromRgb(*colors[0])
        control.model().previewBackground = QColor.fromRgb(*colors[1])

SETTINGSWIN = 'settingsdialog'

class SettingsDialog(QDialog):
    """In order to use a class as an option add it to self.widgets"""
    def __init__(self, controls, parent=None, status=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("puddletag settings")
        winsettings('settingswin', self)

        built_in = [
            (QApplication.translate("Settings", 'General'), GeneralSettings(controls), controls),
            (QApplication.translate("Settings", 'Confirmations'), confirmations.Settings(), None),
            (QApplication.translate("Settings", 'Mappings'), TagMappings(), None),
            (QApplication.translate("Settings", 'Playlist'), Playlist(), None),
            (QApplication.translate("Settings", 'Colours'), ColorEdit(), status['table']),
            (QApplication.translate("Settings", 'Genres'), genres.Genres(status=status), None),
            (QApplication.translate("Settings", 'Tags'), Tags(), status['table']),
            (QApplication.translate("Settings", 'Plugins'), PluginConfig(), None),
            (QApplication.translate("Settings", 'Shortcuts'), ActionEditorDialog(status['actions']), None),]

        d = dict(enumerate(built_in))
            
        i = len(d)
        for control in controls:
            if hasattr(control, SETTINGSWIN):
                c = getattr(control, SETTINGSWIN)(status=status)
                d[i] = [c.title, c, control]
                i += 1
        self._widgets = d

        self.listbox = SettingsList()
        self.model = ListModel(d)
        self.listbox.setModel(self.model)

        self.stack = QStackedWidget()
        self.stack.setFrameStyle(QFrame.StyledPanel)

        self.grid = QGridLayout()
        self.grid.addWidget(self.listbox)
        self.grid.addWidget(self.stack, 0, 1)
        self.grid.setColumnStretch(1, 2)
        self.setLayout(self.grid)

        self.connect(self.listbox, SIGNAL("selectionChanged"), self.showOption)

        selection = QItemSelection()
        self.selectionModel= QItemSelectionModel(self.model)
        index = self.model.index(0,0)
        selection.select(index, index)
        self.listbox.setSelectionModel(self.selectionModel)
        self.selectionModel.select(selection, QItemSelectionModel.Select)

        self.okbuttons = OKCancel()
        self.okbuttons.ok.setDefault(True)
        self.grid.addLayout(self.okbuttons, 1,0,1,2)

        self.connect(self.okbuttons,SIGNAL("ok"), self.saveSettings)
        self.connect(self, SIGNAL("accepted"),self.saveSettings)
        self.connect(self.okbuttons,SIGNAL("cancel"), self.close)

    def showOption(self, option):
        widget = self._widgets[option][1]
        stack = self.stack
        if stack.indexOf(widget) == -1:
            stack.addWidget(widget)
        stack.setCurrentWidget(widget)
        if self.width() < self.sizeHint().width():
            self.setMinimumWidth(self.sizeHint().width())

    def saveSettings(self):
        for z in self._widgets.values():
            try:
                z[1].applySettings(z[2])
            except SettingsError, e:
                QMessageBox.warning(self, 'puddletag',
                    QApplication.translate('Settings', 'An error occurred while saving the settings of <b>%1</b>: %2').arg(z[0]).arg(unicode(e)))
                return
        self.close()

if __name__ == "__main__":
    app=QApplication(sys.argv)
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")
    qb=SettingsDialog()
    qb.show()
    app.exec_()

