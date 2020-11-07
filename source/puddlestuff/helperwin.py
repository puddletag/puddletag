# -*- coding: utf-8 -*-
"""Dialog's that crop up along the application, but are used at at most
one place, and aren't that complicated are put here."""
import os
import sys
from copy import deepcopy

from PyQt5.QtCore import QItemSelectionModel, Qt, pyqtRemoveInputHook, pyqtSignal
from PyQt5.QtGui import QPalette, QBrush, QColor
from PyQt5.QtWidgets import QAbstractItemView, QAction, QApplication, QCheckBox, QComboBox, QCompleter, \
    QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, \
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QVBoxLayout

from . import findfunc, audioinfo
from .audioinfo import commontags, PATH
from .constants import HOMEDIR, KEEP
from .puddleobjects import (
    get_icon, gettaglist, partial,
    settaglist, winsettings, ListButtons, MoveButtons, OKCancel,
    PicWidget, PuddleConfig, natsort_case_key)
from .translations import translate
from .util import pprint_tag
from .util import to_string

ADD, EDIT, REMOVE = (1, 2, 3)
UNCHANGED = 0
BOLD = 1
ITALICS = 2
TAG_DISP = "<b>%s: </b> %s, "


class AutonumberDialog(QDialog):
    newtracks = pyqtSignal(int, int, 'Qt::CheckState', int, str, str, 'Qt::CheckState', name='newtracks')

    def __init__(self, parent=None, minval=0, numtracks=0,
                 enablenumtracks=False):

        QDialog.__init__(self, parent)

        self.setWindowTitle(
            translate('Autonumbering Wizard', "Autonumbering Wizard"))
        winsettings('autonumbering', self)

        def hbox(*widgets):
            box = QHBoxLayout()
            [box.addWidget(z) for z in widgets]
            box.addStretch()
            return box

        vbox = QVBoxLayout()

        self._start = QSpinBox()
        self._start.setValue(minval)
        self._start.setMaximum(65536)

        startlabel = QLabel(translate('Autonumbering Wizard', "&Start: "))
        startlabel.setBuddy(self._start)

        vbox.addLayout(hbox(startlabel, self._start))

        self._padlength = QSpinBox()
        self._padlength.setValue(1)
        self._padlength.setMaximum(65535)
        self._padlength.setMinimum(1)

        label = QLabel(translate('Autonumbering Wizard',
                                 'Max length after padding with zeroes: '))
        label.setBuddy(self._padlength)

        vbox.addLayout(hbox(label, self._padlength))

        self._separator = QCheckBox(translate('Autonumbering Wizard',
                                              "Add track &separator ['/']: Number of tracks"))
        self._numtracks = QSpinBox()
        self._numtracks.setEnabled(False)
        self._numtracks.setMaximum(65535)
        if numtracks:
            self._numtracks.setValue(numtracks)
        self._restart_numbering = QCheckBox(translate('Autonumbering Wizard',
                                                      "&Restart numbering at each directory group."))
        self._restart_numbering.stateChanged.connect(
            self.showDirectorySplittingOptions)

        vbox.addLayout(hbox(self._separator, self._numtracks))
        vbox.addWidget(self._restart_numbering)

        self.custom_numbering_widgets = []

        label = QLabel(translate('Autonumbering Wizard', "Group tracks using pattern:: "))

        self.grouping = QLineEdit()
        label.setBuddy(self.grouping)

        vbox.addLayout(hbox(label, self.grouping))
        self.custom_numbering_widgets.extend([label, self.grouping])

        label = QLabel(translate('Autonumbering Wizard', "Output field: "))

        self.output_field = QComboBox()
        label.setBuddy(self.output_field)

        self.output_field.setEditable(True)
        completer = self.output_field.completer()
        completer.setCaseSensitivity(Qt.CaseSensitive)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)

        self.output_field.setCompleter(completer)
        self.output_field.addItems(gettaglist())
        vbox.addLayout(hbox(label, self.output_field))
        self.custom_numbering_widgets.extend([label, self.output_field])

        self.count_by_group = QCheckBox(translate('Autonumbering Wizard',
                                                  'Increase counter only on group change'))
        vbox.addWidget(self.count_by_group)
        self.custom_numbering_widgets.append(self.count_by_group)

        okcancel = OKCancel()
        vbox.addLayout(okcancel)
        self.setLayout(vbox)

        okcancel.ok.connect(self.emitValuesAndSave)
        okcancel.cancel.connect(self.close)
        self._separator.stateChanged.connect(
            lambda v: self._numtracks.setEnabled(v == Qt.Checked))

        # self._restart_numbering.stateChanged.connect(
        #              self.showDirectorySplittingOptions)

        self._separator.setChecked(enablenumtracks)

        self._loadSettings()

    def showDirectorySplittingOptions(self, state):
        is_checked = state == Qt.Checked
        for widget in self.custom_numbering_widgets:
            widget.setVisible(is_checked)

        if is_checked:
            self._numtracks.setVisible(False)
            self._separator.setText(translate('Autonumbering Wizard',
                                              "Add track &separator ['/']"))
        else:
            self._numtracks.setVisible(True)
            self._separator.setText(translate('Autonumbering Wizard',
                                              "Add track &separator ['/']: Number of tracks"))

    def emitValuesAndSave(self):
        if self._numtracks.isVisible():
            if self._separator.isChecked():
                numtracks = self._numtracks.value()
            else:
                numtracks = -1  # Don't use totals
        else:
            if self._separator.isChecked():
                numtracks = -2  # Use totals, automaticall generated
            else:
                numtracks = -1

        self.close()

        self.newtracks.emit(
            self._start.value(),
            numtracks,
            self._restart_numbering.checkState(),
            self._padlength.value(),
            str(self.grouping.text()),
            str(self.output_field.currentText()),
            self.count_by_group.checkState()
        )

        self._saveSettings()

    def _loadSettings(self):
        cparser = PuddleConfig()
        section = 'autonumbering'
        self._start.setValue(cparser.get(section, 'start', 1))
        self._separator.setCheckState(
            cparser.get(section, 'separator', Qt.Unchecked))
        self._padlength.setValue(cparser.get(section, 'padlength', 1))

        self._restart_numbering.setCheckState(
            cparser.get(section, 'restart', Qt.Unchecked))

        self.count_by_group.setCheckState(
            cparser.get(section, 'count_by_group', Qt.Unchecked))

        self.showDirectorySplittingOptions(self._restart_numbering.checkState())

        self.grouping.setText(cparser.get(section, 'grouping', '%__dirpath%'))

        output_field_text = cparser.get(section, 'output_field', 'track')
        if not output_field_text:
            output_field_text = 'track'

        last_output_field_index = self.output_field.findText(output_field_text)
        if last_output_field_index > -1:
            self.output_field.setCurrentIndex(last_output_field_index)

    def _saveSettings(self):
        cparser = PuddleConfig()
        section = 'autonumbering'
        cparser.set(section, 'start', self._start.value())
        cparser.set(section, 'separator', self._separator.checkState())
        cparser.set(section, 'count_by_group', self.count_by_group.checkState())
        cparser.set(section, 'numtracks', self._numtracks.value())
        cparser.set(section, 'restart', self._restart_numbering.checkState())
        cparser.set(section, 'padlength', self._padlength.value())
        cparser.set(section, 'grouping', self.grouping.text())
        cparser.set(section, 'output_field', self.output_field.currentText())


class ImportTextFile(QDialog):
    """Dialog that importing a text file to retrieve tags from."""
    Newtags = pyqtSignal(list, str, name='Newtags')

    def __init__(self, parent=None, filename=None, clipboard=None):
        QDialog.__init__(self, parent)

        self.setWindowTitle(
            translate('Text File -> Tag', "Import tags from text file"))
        winsettings('importwin', self)

        grid = QGridLayout()

        self.label = QLabel(translate('Text File -> Tag', "Text"))
        grid.addWidget(self.label, 0, 0)

        self.label = QLabel(translate('Text File -> Tag', "Tag preview"))
        grid.addWidget(self.label, 0, 2)

        self.file = QTextEdit()
        grid.addWidget(self.file, 1, 0, 1, 2)

        self.tags = QTextEdit()
        grid.addWidget(self.tags, 1, 2, 1, 2)
        self.tags.setLineWrapMode(QTextEdit.NoWrap)

        hbox = QHBoxLayout()

        self.patterncombo = QComboBox()
        self.patterncombo.setEditable(True)
        self.patterncombo.setDuplicatesEnabled(False)

        okcancel = OKCancel()
        self.ok = okcancel.okButton
        self.cancel = okcancel.cancelButton

        self.openfile = QPushButton(
            translate('Text File -> Tag', "&Select File"))
        getclip = QPushButton(
            translate('Text File -> Tag', "&Paste Clipboard"))
        getclip.clicked.connect(self.openClipBoard)

        hbox.addWidget(self.openfile)
        hbox.addWidget(getclip)
        hbox.addWidget(self.patterncombo, 1)
        hbox.addLayout(okcancel)

        grid.addLayout(hbox, 3, 0, 1, 4)
        self.setLayout(grid)

        self.openfile.clicked.connect(self.openFile)
        self.cancel.clicked.connect(self.close)
        self.ok.clicked.connect(self.emitValues)

        if clipboard:
            self.openClipBoard()
            return

        self.lastDir = HOMEDIR

        if filename is not None:
            self.openFile(filename)

    def emitValues(self):
        """When I'm done, emit a signal with the updated tags."""
        self.close()
        self.Newtags.emit(self.dicttags,
                          str(self.patterncombo.currentText()))

    def fillTags(self, string=None):  # string is there purely for the SIGNAL
        """Fill the tag textbox."""

        def formattag(tags):
            if tags:
                return pprint_tag(tags, TAG_DISP, True)[:-2]
            else:
                return ""

        self.dicttags = []
        self.tags.clear()
        for z in self.lines.split("\n"):
            self.dicttags.append(findfunc.filenametotag(
                str(self.patterncombo.currentText()), z, False, False))
        if self.dicttags:
            self.tags.setHtml(
                "<br/>".join([formattag(z) for z in self.dicttags]))

    def openFile(self, filename=None, dirpath=None):
        """Open the file and fills the textboxes."""
        if not dirpath:
            dirpath = self.lastDir

        if not filename:
            selectedFile = QFileDialog.getOpenFileName(self,
                                                       'OpenFolder', dirpath)
            filename = selectedFile[0]

        if not filename:
            return True

        try:
            f = open(filename, 'r')
        except (IOError, OSError) as detail:
            errormsg = translate('Text File -> Tag',
                                 "The file <b>%1</b> couldn't be loaded.<br /> "
                                 "Do you want to choose another?")

            ret = QMessageBox.question(self,
                                       translate('Text File -> Tag', "Error"),
                                       translate('Text File -> Tag', errormsg.arg(filename)))

            if ret == QMessageBox.Yes:
                return self.openFile()
            else:
                return detail

        self.lines = f.readlines()
        self.file.setPlainText("".join(self.lines))
        self.setLines()
        self.fillTags()
        self.show()
        self.file.textChanged.connect(self.setLines)
        self.patterncombo.editTextChanged.connect(
            self.fillTags)
        self.lastDir = os.path.dirname(filename)

    def openClipBoard(self):
        text = str(QApplication.clipboard().text())
        self.lines = text.split('\n')
        self.file.setPlainText(text)
        self.setLines()
        self.fillTags()
        self.show()
        self.file.textChanged.connect(self.setLines)
        self.patterncombo.editTextChanged.connect(self.fillTags)

    def setLines(self):
        self.lines = str(self.file.document().toPlainText())
        self.fillTags()


class TextEdit(QPlainTextEdit):
    def focusInEvent(self, event):
        super(TextEdit, self).focusInEvent(event)
        self.selectAll()
        pos = len(self.toPlainText()) - 1
        if pos > 0:
            self.textCursor().setPosition(pos)
        else:
            self.textCursor().setPosition(0)

    def focusOutEvent(self, event):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super(TextEdit, self).focusOutEvent(event)


class EditField(QDialog):
    """Dialog that allows editing of a field and it's values.

    When the user clicks ok, a 'donewithmyshit' (yeah yeah,
    I wrote this three years ago) signal
    is emitted containing three parameters.

    The first being the new field, the second that field's
    value and the third is the dictionary of the previous field
    in the form {field: value}.
    (Because the user might choose to edit a different tag,
    then the one that was chosen and you'd want to delete that one)"""
    donewithmyshit = pyqtSignal(str, str, object, name='donewithmyshit')

    def __init__(self, field=None, parent=None, field_list=None, edit=True):

        QDialog.__init__(self, parent)
        self.setWindowTitle(translate('Edit Field', 'Edit Field'))
        winsettings('edit_field', self)

        self.vbox = QVBoxLayout()

        label = QLabel(translate('Edit Field', "&Field"))
        self.tagcombo = QComboBox()
        self.tagcombo.setEditable(True)
        label.setBuddy(self.tagcombo)
        completer = self.tagcombo.completer()
        completer.setCaseSensitivity(Qt.CaseSensitive)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.tagcombo.setCompleter(completer)
        self.tagcombo.addItems(field_list if field_list else gettaglist())

        # Get the previous field
        self.__oldField = field
        label1 = QLabel(translate('Edit Field', "&Value"))
        self.value = TextEdit()
        self.value.setTabChangesFocus(True)
        label1.setBuddy(self.value)

        okcancel = OKCancel()
        okcancel.okButton.setText(translate('Edit Field', 'A&dd'))

        if field is not None:
            x = self.tagcombo.findText(field[0])

            if x > -1:
                self.tagcombo.setCurrentIndex(x)
            else:
                self.tagcombo.setEditText(field[0])
            self.value.setPlainText(field[1])
            if edit:
                okcancel.okButton.setText(translate('Edit Field', 'E&dit'))

        list(map(self.vbox.addWidget, [label, self.tagcombo, label1, self.value]))

        self.vbox.addLayout(okcancel)
        self.setLayout(self.vbox)

        okcancel.ok.connect(self.ok)
        okcancel.cancel.connect(self.close)

        self.value.setFocus() if self.__oldField else self.tagcombo.setFocus()

    def ok(self):
        self.close()
        self.donewithmyshit.emit(
            str(self.tagcombo.currentText()),
            str(self.value.toPlainText()),
            self.__oldField)


class StatusWidgetItem(QTableWidgetItem):
    def __init__(self, text=None, status=None, colors=None, preview=False):
        QTableWidgetItem.__init__(self)
        self.preview = preview
        self.statusColors = colors

        if text:
            self.setText(text)

        if status and status in self.statusColors:
            self.setBackground(self.statusColors[status])

        self._status = status
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self._original = (text, preview, status)
        self.linked = []

    def _get_preview(self):
        return self.font().bold()

    def _set_preview(self, value):
        font = self.font()
        font.setBold(value)
        self.setFont(font)

    preview = property(_get_preview, _set_preview)

    def _get_status(self):
        return self._status

    def _set_status(self, status):
        if status and status in self.statusColors:
            if self._status == ADD and status != REMOVE:
                return
            self.setBackground(self.statusColors[status])
            self._status = status
        else:
            self.setBackground(QTableWidgetItem().background())
            self._status = None

    status = property(_get_status, _set_status)

    def __lt__(self, item):
        if self.text().upper() < item.text().upper():
            return True
        return False

    def reset(self):
        self.setText(self._original[0])
        self.preview = self._original[1]
        status = self._original[2]
        if status == ADD:
            self.status = REMOVE
        else:
            self.status = status
        self.linked = []


class VerticalHeader(QHeaderView):
    def __init__(self, parent=None):
        QHeaderView.__init__(self, Qt.Vertical, parent)
        self.setDefaultSectionSize(self.minimumSectionSize() + 4)
        self.setMinimumSectionSize(1)

        self.sectionResized.connect(
            self._resize)

    def _resize(self, row, oldsize, newsize):
        self.setDefaultSectionSize(newsize)


class StatusWidgetCombo(QComboBox):
    def __init__(self, items=None, status=None, colors=None, preview=False):
        QComboBox.__init__(self)
        self.preview = preview

        self.statusColors = colors
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLength)

        items = map(str, items)
        items = sorted(items, key=natsort_case_key)
        if len(items) > 1:
            items.append(r'\\'.join(items))
        self.addItem(KEEP)
        self.addItems(items)
        self.setCurrentIndex(0)

        if status and status in self.statusColors:
            self.setBackground(self.statusColors[status])
        else:
            self.setBackground(None)

        self._status = status
        self._original = (items, preview, status)
        self.linked = []

    def _get_preview(self):
        return False
        return self.font().bold()

    def _set_preview(self, value):
        return
        font = self.font()
        font.setBold(value)
        self.setFont(font)

    preview = property(_get_preview, _set_preview)

    def _get_status(self):
        return self._status

    def _set_status(self, status):
        if status and status in self.statusColors:
            if self._status == ADD and status != REMOVE:
                return
            self.setBackground(self.statusColors[status])
            self._status = status
        else:
            self.setBackground(None)
            self._status = None

    status = property(_get_status, _set_status)

    def setBackground(self, brush=None):
        if brush is None:
            color = QLineEdit().palette().color(QPalette.Base).name()
        else:
            color = brush.color().name()
        self.setStyleSheet("QComboBox { background-color: %s; }" % color);

    def background(self):
        brush = QBrush()
        brush.setColor(self.palette().color(QPalette.Background))
        return brush

    def reset(self):
        self.clear()
        self.addItems(self._original[0])
        self.setCurrentIndex(0)
        self.preview = self._original[1]
        status = self._original[2]
        if status == ADD:
            self.status = REMOVE
        else:
            self.status = status
        self.linked = []

    def setText(self, value):
        if self.currentIndex() == 0:
            self.insertItem(1, value)
            self.setCurrentIndex(1)
        else:
            self.setItemText(self.currentIndex(), value)


class ExTags(QDialog):
    """A dialog that shows you the tags in a file

    In addition, any attached cover art is shown."""
    rowChanged = pyqtSignal(object, name='rowChanged')
    extendedtags = pyqtSignal(dict, name='extendedtags')

    def __init__(self, parent=None, row=None, files=None, preview_mode=False,
                 artwork=True, status=None):

        if status is None:
            status = {'cover_pattern': 'folder'}

        self.status = status

        QDialog.__init__(self, parent)
        winsettings('extendedtags', self)
        self.get_fieldlist = []
        self.previewMode = preview_mode

        add = QColor.fromRgb(255, 255, 0)
        edit = QColor.fromRgb(0, 255, 0)
        remove = QColor.fromRgb(255, 0, 0)
        self._colors = {ADD: QBrush(add),
                        EDIT: QBrush(edit), REMOVE: QBrush(remove)}

        self.table = QTableWidget(0, 2, self)
        self.table.setVerticalHeader(VerticalHeader())
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setHorizontalHeaderLabels([
            translate('Extended Tags', 'Field'),
            translate('Extended Tags', 'Value')])

        header = self.table.horizontalHeader()
        header.setVisible(True)
        header.setSortIndicatorShown(True)
        header.setStretchLastSection(True)
        header.setSortIndicator(0, Qt.AscendingOrder)

        self.piclabel = PicWidget(buttons=True)
        self.piclabel.imageChanged.connect(
            self._imageChanged)

        if not isinstance(self.piclabel.removepic, QAction):
            self.piclabel.removepic.clicked.connect(
                self.removePic)
        else:
            self.piclabel.removepic.triggered.connect(self.removePic)

        if row and row >= 0 and files:
            buttons = MoveButtons(files, row)
            buttons.indexChanged.connect(self._prevnext)
            buttons.setVisible(True)
        else:
            buttons = MoveButtons([], row)
            buttons.setVisible(False)

        self._files = files

        self.okcancel = OKCancel()
        self.okcancel.insertWidget(0, buttons)

        self._reset = QToolButton()
        self._reset.setToolTip(translate('Extended Tags',
                                         'Resets the selected fields to their original value.'))
        self._reset.setIcon(get_icon('edit-undo', ':/undo.png'))
        self._reset.clicked.connect(self.resetFields)

        self.listbuttons = ListButtons()
        self.listbuttons.layout().addWidget(self._reset)
        self.listbuttons.moveupButton.hide()
        self.listbuttons.movedownButton.hide()

        listframe = QFrame()
        listframe.setFrameStyle(QFrame.Box)
        hbox = QHBoxLayout()
        hbox.addWidget(self.table, 1)
        hbox.addLayout(self.listbuttons, 0)
        listframe.setLayout(hbox)

        layout = QVBoxLayout()
        if artwork:
            imageframe = QFrame()
            imageframe.setFrameStyle(QFrame.Box)
            vbox = QVBoxLayout()
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.addWidget(self.piclabel)
            vbox.addStretch()
            vbox.addStrut(0)
            imageframe.setLayout(vbox)

            hbox = QHBoxLayout()
            hbox.addWidget(listframe, 1)
            hbox.addSpacing(4)
            hbox.addWidget(imageframe)
            hbox.addStrut(1)
            layout.addLayout(hbox)
        else:
            layout.addWidget(listframe)

        layout.addLayout(self.okcancel)
        self.setLayout(layout)

        self.okcancel.cancel.connect(self.closeMe)
        self.table.itemDoubleClicked.connect(self.editField)
        self.table.itemSelectionChanged.connect(self._checkListBox)
        self.okcancel.ok.connect(self.okClicked)

        self.listbuttons.edit.connect(self.editField)
        self.listbuttons.addButton.clicked.connect(self.addField)
        self.listbuttons.removeButton.clicked.connect(self.removeField)
        self.listbuttons.duplicate.connect(self.duplicate)

        self.setMinimumSize(450, 350)

        self.canceled = False
        self.filechanged = False

        if row and row >= 0 and files:
            self._prevnext(row)
        else:
            self.loadFiles(files)

    def addField(self):
        win = EditField(parent=self, field_list=self.get_fieldlist)
        win.setModal(True)
        win.show()
        win.donewithmyshit.connect(self.editFieldBuddy)

    def _checkListBox(self):
        if self.table.rowCount() <= 0:
            self.table.setEnabled(False)
            self.listbuttons.editButton.setEnabled(False)
            self.listbuttons.removeButton.setEnabled(False)
            self.listbuttons.duplicateButton.setEnabled(False)
            self._reset.setEnabled(False)
        else:
            self.table.setEnabled(True)
            self._reset.setEnabled(True)
            if len(self.table.selectedIndexes()) / 2 > 1:
                self.listbuttons.editButton.setEnabled(False)
                self.listbuttons.duplicateButton.setEnabled(False)
            else:
                self.listbuttons.editButton.setEnabled(True)
                self.listbuttons.removeButton.setEnabled(True)
                self.listbuttons.duplicateButton.setEnabled(True)
        self.table.resizeColumnToContents(0)

    def closeEvent(self, event):
        self.piclabel.close()
        QDialog.closeEvent(self, event)

    def closeMe(self):
        self.canceled = True
        self.close()

    def _deletePressed(self, item):
        if self.table.deletePressed:
            self.table.deletePressed = False
            self.removeField()

    def duplicate(self):
        self.editField(True)

    def editField(self, duplicate=False):
        """Opens a dialog to edit the currently selected Field.

        If duplicate is True the Edit Field dialog will be populated
        with the currently selected field's values. The new field'll then
        be added to the field list."""
        row = self.table.currentRow()
        if row != -1:
            prevtag = self.get_field(row)
            if duplicate is True:
                win = EditField(prevtag, self, self.get_fieldlist, edit=False)
            else:
                win = EditField(prevtag, self, self.get_fieldlist)
            win.setModal(True)
            win.show()

            # Have to check for truth, because this method is
            # called by the doubleclicked signal.
            if duplicate is True:
                buddy = partial(self.editFieldBuddy, duplicate=True)
            else:
                buddy = self.editFieldBuddy
            win.donewithmyshit.connect(buddy)

    def editFieldBuddy(self, tag, value, prevtag=None, duplicate=False):
        rowcount = self.table.rowCount()
        if prevtag is not None:
            if duplicate:
                row = rowcount
                self._settag(rowcount, tag, value, ADD,
                             self.previewMode, True)
            else:
                if tag == prevtag[0]:
                    row = self.table.currentRow()
                    self._settag(row, tag, value, EDIT,
                                 self.previewMode, True)
                    if row + 1 < rowcount:
                        self.table.selectRow(row + 1)
                else:
                    cur_item = self.table.item(self.table.currentRow(), 0)
                    self.resetFields([cur_item])
                    self.table.setCurrentItem(cur_item,
                                              QItemSelectionModel.ClearAndSelect)
                    self.table.selectRow(self.table.row(cur_item))
                    self.removeField()
                    valitem = self._settag(rowcount, tag,
                                           value, ADD, self.previewMode, True)
                    cur_item.linked = [valitem]
        else:
            self._settag(rowcount, tag, value, ADD, self.previewMode, True)
        self._checkListBox()
        self.filechanged = True
        self.table.clearSelection()

    def get_field(self, row, status=None):
        getitem = self.table.item
        item = getitem(row, 0)
        tag = str(item.text())
        try:
            value = str(getitem(row, 1).text())
        except AttributeError:
            value = str(self.table.cellWidget(row, 1).currentText())
        if status:
            return (tag, value, item.status)
        else:
            return (tag, value)

    def _imageChanged(self):
        self.filechanged = True

    def loadSettings(self):
        cparser = PuddleConfig()
        self.get_fieldlist = gettaglist()
        get = lambda k, v: cparser.get('extendedtags', k, v, True)
        add = QColor.fromRgb(*get('add', [255, 255, 0]))
        edit = QColor.fromRgb(*get('edit', [0, 255, 0]))
        remove = QColor.fromRgb(*get('remove', [255, 0, 0]))

        self._colors = {ADD: QBrush(add),
                        EDIT: QBrush(edit), REMOVE: QBrush(remove)}

        item = self.table.item
        for row in range(self.table.rowCount()):
            field_item = self.get_item(row, 0)
            field_item.statusColors = self._colors
            field_item.status = field_item.status

            val_item = self.get_item(row, 1)
            val_item.statusColors = self._colors
            val_item.status = val_item.status

    def listtotag(self):
        get_field = self.get_field
        tags = {}
        lowered = {}
        listitems = [get_field(row, True) for row
                     in range(self.table.rowCount())]

        for field, val, status in listitems:
            if status != REMOVE:
                if val == KEEP:
                    continue
                l_field = field.lower()
                if l_field in lowered:
                    tags[lowered[l_field]].append(val)
                else:
                    lowered[l_field] = field
                    tags[field] = [z.strip() for z in val.split('\\') if z.strip()]
            else:
                if field.lower() not in lowered:
                    tags[field] = []
                    lowered[field.lower()] = field
        return tags

    def loadFiles(self, audios):
        if self.filechanged:
            self.save()
        self.filechanged = False
        self.table.clearContents()
        self.table.setRowCount(0)
        self.piclabel.lastfilename = audios[0].filepath
        self.piclabel.setEnabled(False)
        self.piclabel.setImages(None)

        if len(audios) == 1:
            audio = audios[0]
            self.setWindowTitle(audios[0].filepath)
            self._loadsingle(audio)
        else:
            self.setWindowTitle(
                translate('Extended Tags', 'Different files.'))

            from .tagmodel import status
            k = status['table'].model().taginfo[0]
            common, numvalues, imagetags = commontags(audios)
            images = common['__image']
            del (common['__image'])
            previews = set(audios[0].preview)
            italics = set(audios[0].equal_fields())
            self.piclabel.currentFile = audios[0]
            self.piclabel.filePattern = self.status['cover_pattern']

            for audio in audios[1:]:
                previews = previews.intersection(audio.preview)
                italics = italics.intersection(audio.equal_fields())

            row = 0

            for field, values in common.items():
                if field in italics:
                    preview = UNCHANGED
                # field in italics => field in previews.
                elif field in previews:
                    preview = BOLD
                else:
                    preview = UNCHANGED
                if numvalues[field] != len(audios):
                    self._settag(row, field, values, multi=True)
                    row += 1
                else:
                    if isinstance(values, str):
                        self._settag(row, field, values, None, preview)
                        row += 1
                    else:
                        for v in values:
                            self._settag(row, field, v, None, preview)
                            row += 1

            self.piclabel.setImageTags(imagetags)
            if images:
                self.piclabel.setEnabled(True)
                self.piclabel.setImages(images)
            else:
                self.piclabel.setImages(None)
                self.piclabel.setEnabled(True)
                if images == 0:
                    self.piclabel.context = 'Cover Varies'
                    self.piclabel.removepic.setEnabled(True)
        self._checkListBox()

    def _loadsingle(self, tags):
        items = []
        d = tags.usertags.copy()
        italics = tags.equal_fields()
        self.piclabel.currentFile = tags
        self.piclabel.filePattern = self.status['cover_pattern']

        for key, val in sorted(d.items()):
            if key in italics:
                preview = UNCHANGED
            elif key in tags.preview:
                preview = BOLD
            else:
                preview = UNCHANGED
            if isinstance(val, str):
                items.append([key, val, None, preview])
            else:
                [items.append([key, z, None, preview]) for z in val]

        [self._settag(i, *item) for i, item in enumerate(items)]

        self.piclabel.lastfilename = tags.filepath
        if not tags.library:
            self.piclabel.setImageTags(tags.IMAGETAGS)
            if tags.IMAGETAGS:
                if '__image' in tags.preview:
                    images = tags.preview['__image']
                else:
                    images = tags.images
                self.piclabel.setEnabled(True)
                if images:
                    self.piclabel.setImages(deepcopy(images))
                else:
                    self.piclabel.setImages(None)
        self._checkListBox()
        self.setWindowTitle(tags[PATH])

    def okClicked(self):
        self.save()
        self.close()

    def _prevnext(self, row):
        if self.filechanged:
            self.save()
        self.loadFiles([self._files[row]])
        self.rowChanged.emit(row)

    def get_item(self, row, column=None):
        if column is None:  # Assume QModelIndex passed
            column = row.column()
            row = row.row()
        item = self.table.item(row, column)
        if item is None:
            item = self.table.cellWidget(row, column)
        return item

    def removeField(self):
        tb = self.table
        tb.setSortingEnabled(False)
        to_remove = {}
        rows = []
        for index in self.table.selectedIndexes():
            row = index.row()
            item = self.get_item(index)
            if item.status == ADD:
                to_remove[row] = item
            rows.append(row)
            item.status = REMOVE
            item.status = REMOVE
        [tb.removeRow(tb.row(z)) for z in to_remove.values()]
        tb.setSortingEnabled(True)
        self.filechanged = True
        self._checkListBox()
        if rows:
            row = max(rows)
            self.table.clearSelection()
            if row + 1 < self.table.rowCount():
                self.table.selectRow(row + 1)

    def resetFields(self, items=None):
        box = self.table
        to_remove = {}  # Stores row: item values so that only one item
        # gets removed per row.

        max_row = -1
        for index in box.selectedIndexes():
            row = index.row()
            item = self.table.item(row, index.column())
            if item is None:
                item = self.table.cellWidget(row, index.column())
            for i in item.linked:
                try:
                    to_remove[box.row(i)] = i
                except RuntimeError:
                    pass
            item.reset()
            if row > max_row:
                max_row = row
            if item.status == REMOVE:
                to_remove[row] = item

        self.table.clearSelection()
        if max_row != -1 and max_row + 1 < self.table.rowCount():
            self.table.selectRow(max_row + 1)

        for item in to_remove.values():
            self.table.removeRow(self.table.row(item))
        self._checkListBox()

    def removePic(self):
        if self.piclabel.context == 'Cover Varies':
            self.piclabel.context = 'No Images'
            self.piclabel.removepic.setEnabled(False)
            if not isinstance(self.piclabel.removepic, QAction):
                self.piclabel.removepic.clicked.disconnect(
                    self.removePic)
            else:
                self.piclabel.removepic.triggered.disconnect(self.removePic)

            self.piclabel.setImages(None)

    def save(self):

        if not self.filechanged:
            table = self.table
            for row in range(table.rowCount()):
                combo = table.cellWidget(row, 1)
                if combo is not None and combo.currentIndex() != 0:
                    self.filechanged = True
                    break

        if not self.filechanged:
            return

        tags = self.listtotag()
        if self.piclabel.context != 'Cover Varies':
            if not self.piclabel.images:
                tags['__image'] = []
            else:
                tags["__image"] = self.piclabel.images
        newtags = [z for z in tags if z not in self.get_fieldlist]
        if newtags and newtags != ['__image']:
            settaglist(newtags + self.get_fieldlist)
        self.extendedtags.emit(tags)

    def _settag(self, row, field, value, status=None, preview=False,
                check=False, multi=False):

        tb = self.table
        tb.setSortingEnabled(False)
        if row >= tb.rowCount():
            tb.insertRow(row)
            field_item = StatusWidgetItem(field, status,
                                          self._colors, preview)
            tb.setItem(row, 0, field_item)
            if not multi and (len(value) == 1 or isinstance(value, str)):
                valitem = StatusWidgetItem(to_string(value), status, self._colors, preview)
                tb.setItem(row, 1, valitem)
            else:
                valitem = StatusWidgetCombo(value, status, self._colors, preview)
                tb.setCellWidget(row, 1, valitem)
        else:
            field_item = tb.item(row, 0)
            field_item.setText(field)
            field_item.status = status

            val_item = self.get_item(row, 1)
            val_item.setText(value)
            val_item.status = status

        if check:
            lowered_tag = field.lower()
            for row in range(tb.rowCount()):
                item = tb.item(row, 0)
                text = str(item.text())
                if text != field and text.lower() == lowered_tag:
                    item.setText(field)
                    if item.status not in [ADD, REMOVE]:
                        item.status = EDIT
                        try:
                            tb.item(row, 1).status = EDIT
                        except AttributeError:
                            tb.cellWidget(row, 1).status = EDIT

        tb.setSortingEnabled(True)
        return field_item


class ConfirmationErrorDialog(QDialog):
    def __init__(self, name, parent=None):
        super(ConfirmationErrorDialog, self).__init__(parent)
        self.name = name
        self.__label = QLabel()
        icon = QLabel()
        msgbox = QMessageBox()
        msgbox.setIcon(QMessageBox.Warning)
        icon.setPixmap(msgbox.iconPixmap())
        ok = QPushButton(translate("Defaults", "OK"))
        checkbox = QCheckBox(
            translate("Defaults", "Never show this message again."))

        ok.clicked.connect(partial(self.saveState, name))

        labelbox = QHBoxLayout()
        labelbox.addWidget(icon)
        labelbox.addWidget(self.__label)

        layout = QVBoxLayout()
        layout.addLayout(labelbox, 1)
        layout.addWidget(checkbox, 0, Qt.AlignHCenter)
        layout.addWidget(ok, 0, Qt.AlignHCenter)
        layout.addStretch()
        self.setLayout(layout)

    def saveState(self, name):
        settings = PuddleConfig()
        settings.set("OnceOnlyErrors", name, True)
        self.close()

    def showMessage(self, message):
        settings = PuddleConfig()
        should_show = settings.get("OnceOnlyErrors", self.name, True)
        self.__label.setText(message)
        if should_show:
            self.setModal(True)
            self.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dirpath = '/home/keith/Desktop/Daft.Punk-Random.Access.Memories-2013-FLAC.-NewsHost-1023'
    import glob

    tags = list(map(audioinfo.Tag, glob.glob(os.path.join(dirpath, "*.flac"))))
    for tag in tags:
        tag.preview = {}
        tag.equal_fields = lambda: []
        tag.library = None
    wid = ExTags(files=tags)
    wid.resize(200, 400)
    wid.show()
    pyqtRemoveInputHook()
    app.exec_()
