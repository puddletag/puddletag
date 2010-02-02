#!/usr/bin/env python
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
from puddleobjects import ListButtons, OKCancel, HeaderSetting, ListBox, PuddleConfig, winsettings
import pdb
import audioinfo.util

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
        QCheckBox.__init__(self, text, parent)

        self.settingValue = default

    def _value(self):
        if self.checkState() == Qt.Checked:
            return unicode(self.text()), True
        else:
            return unicode(self.text()), False

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
        label = QLabel(desc)
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
        vbox.addStretch()
        self.setLayout(vbox)

    def applySettings(self, controls):
        vals =  dict([c.settingValue for c in self._controls])
        for c in controls:
            if hasattr(c, 'applyGenSettings'):
                c.applyGenSettings(vals)
        save_gen_settings(vals)

class TagMappings(QWidget):
    def __init__(self, parent = None):
        filename = os.path.join(PuddleConfig().savedir, 'mappings')
        self._mappings = audioinfo.mapping

        QWidget.__init__(self, parent)
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(['Tag', 'Source', 'Target'])
        header = self._table.horizontalHeader()
        header.setVisible(True)
        self._table.verticalHeader().setVisible(False)
        header.setStretchLastSection(True)
        buttons = ListButtons()
        buttons.connectToWidget(self)
        buttons.moveup.setVisible(False)
        buttons.movedown.setVisible(False)

        hbox = QHBoxLayout()
        hbox.addWidget(self._table, 1)
        hbox.addLayout(buttons, 0)
        self.setLayout(hbox)
        self._setMappings(self._mappings)

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
        self._table.insertRow(row)
        for column, v in enumerate(['Tag', 'Source', 'Target']):
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
            original = itemtext(row, 1).lower()
            other = itemtext(row, 2).lower()
            text.append((tag, original, other))
            if tag in mappings:
                mappings[tag].update({other: original})
            else:
                mappings[tag] = {other: original}
        self._mappings = mappings
        filename = os.path.join(PuddleConfig().savedir, 'mappings')
        f = open(filename, 'w')
        f.write('\n'.join([' '.join(z) for z in text]))
        f.close()


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

SETTINGSWIN = 'settingsdialog'

class SettingsDialog(QDialog):
    """In order to use a class as an option add it to self.widgets"""
    def __init__(self, controls, parent=None, status=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("puddletag settings")
        winsettings('settingswin', self)

        d = {0: ('General', GeneralSettings(controls), controls),
             1: ('Mappings', TagMappings(), None)}
        i = 2
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
        self.grid.addWidget(self.stack,0,1)
        self.grid.setColumnStretch(1,2)
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
            z[1].applySettings(z[2])
        self.close()

if __name__ == "__main__":
    app=QApplication(sys.argv)
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")
    qb=SettingsDialog()
    qb.show()
    app.exec_()

