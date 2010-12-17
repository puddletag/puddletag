# -*- coding: utf-8 -*-
"""Dialog's that crop up along the application, but are used at at most
one place, and aren't that complicated are put here."""

#helperwin.py

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


from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys, findfunc, audioinfo, os,pdb, resource
from puddleobjects import (gettaglist, settaglist, OKCancel, partial, MoveButtons, ListButtons,
    PicWidget, winsettings, PuddleConfig, get_icon)
from copy import deepcopy
from puddlestuff.constants import HOMEDIR
ADD, EDIT, REMOVE = (1, 2, 3)
UNCHANGED = 0
BOLD = 1
ITALICS = 2
from audioinfo import commontags, INFOTAGS, REVTAGS, PATH
from functools import partial

tr = QApplication.trUtf8

class TrackWindow(QDialog):
    """Dialog that allows automatic numbering of tracks.
    Number the tracks in range(start, end)

    Emit's the signal 'newtracks' containing a list of two items when it's closed:
    the from value and the to value(a unicode string). If no to value
    was specified then the to value is an empty string ('')"""
    def __init__(self, parent=None, minval=0, numtracks = 0, enablenumtracks = False):
        QDialog.__init__(self,parent)
        #tr = partial(QApplication.trUtf8, "Autonumbering Wizard")
        
        self.setWindowTitle(QApplication.translate('Autonumbering Wizard', "Autonumbering Wizard"))
        winsettings('autonumbering', self)

        def hbox(*widgets):
            box = QHBoxLayout()
            [box.addWidget(z) for z in widgets]
            box.addStretch()
            return box

        vbox = QVBoxLayout()
        
        startlabel = QLabel(QApplication.translate('Autonumbering Wizard', "Start: "))
        self._start = QSpinBox()
        startlabel.setBuddy(self._start)
        self._start.setValue(minval)
        self._start.setMaximum(65536)

        vbox.addLayout(hbox(startlabel, self._start))

        label = QLabel(QApplication.translate('Autonumbering Wizard', 'Max length after padding with zeroes: '))
        self._padlength = QSpinBox()
        label.setBuddy(self._padlength)
        self._padlength.setValue(1)
        self._padlength.setMaximum(65535)
        self._padlength.setMinimum(1)
        vbox.addLayout(hbox(label, self._padlength))

        self._separator = QCheckBox(QApplication.translate('Autonumbering Wizard', "Add track &separator ['/']: Number of tracks"))
        self._numtracks = QSpinBox()
        self._numtracks.setEnabled(False)
        if numtracks:
            self._numtracks.setValue(numtracks)
        self._restart_numbering = QCheckBox(QApplication.translate('Autonumbering Wizard', "&Restart numbering at each directory."))

        vbox.addLayout(hbox(self._separator, self._numtracks))
        vbox.addWidget(self._restart_numbering)

        okcancel = OKCancel()
        vbox.addLayout(okcancel)
        self.setLayout(vbox)

        self.connect(okcancel,SIGNAL('ok'), self.doStuff)
        self.connect(okcancel,SIGNAL('cancel'),self.close)
        self.connect(self._separator, SIGNAL("stateChanged(int)"), self.setEdit)

        if enablenumtracks:
            self._separator.setCheckState(Qt.Checked)
        else:
            self._separator.setCheckState(Qt.Unchecked)

        self._loadSettings()

    def _loadSettings(self):
        cparser = PuddleConfig()
        section = 'autonumbering'
        self._start.setValue(cparser.get(section, 'start', 1))
        self._separator.setCheckState(cparser.get(section, 'separator', Qt.Unchecked))
        self._numtracks.setValue(cparser.get(section, 'numtracks', 1))
        self._padlength.setValue(cparser.get(section, 'padlength',1))
        self._restart_numbering.setCheckState(cparser.get(section, 'restart',
            Qt.Unchecked))

    def setEdit(self, val):
        #print val
        if val == Qt.Checked:
            self._numtracks.setEnabled(True)
        else:
            self._numtracks.setEnabled(False)

    def doStuff(self):
        self.close()
        if self._separator.checkState() == Qt.Checked:
            self.emit(SIGNAL("newtracks"), self._start.value(),
                        self._numtracks.value(),
                        self._restart_numbering.checkState(),
                        self._padlength.value())
        else:
            self.emit(SIGNAL("newtracks"), self._start.value(),
                        None, self._restart_numbering.checkState(),
                        self._padlength.value())
        self._saveSettings()

    def _saveSettings(self):
        cparser = PuddleConfig()
        section = 'autonumbering'
        cparser.set(section, 'start', self._start.value())
        cparser.set(section, 'separator', self._separator.checkState())
        cparser.set(section, 'numtracks', self._numtracks.value())
        cparser.set(section, 'restart', self._restart_numbering.checkState())
        cparser.set(section, 'padlength', self._padlength.value())
        

class ImportWindow(QDialog):
    """Dialog that allows you to import a file to tags.

    emits a signal newtags with a dictionary containing
    the...new tags."""
    def __init__(self,parent = None, filename = None, clipboard = None):
        QDialog.__init__(self, parent)
        
        self.setWindowTitle(QApplication.translate('Text File -> Tag', "Import tags from file"))
        winsettings('importwin', self)

        self.grid = QGridLayout()

        self.label = QLabel(QApplication.translate('Text File -> Tag', "Text"))
        self.grid.addWidget(self.label,0,0)

        self.label = QLabel(QApplication.translate('Text File -> Tag', "Tag preview"))
        self.grid.addWidget(self.label,0,2)


        self.file = QTextEdit()
        self.grid.addWidget(self.file,1,0,1,2)

        self.tags = QTextEdit()
        self.grid.addWidget(self.tags,1,2,1,2)
        self.tags.setLineWrapMode(QTextEdit.NoWrap)

        #self.label = QLabel("Pattern")
        #self.grid.addWidget(self.label,2,0,)

        self.hbox = QHBoxLayout()

        self.patterncombo = QComboBox()
        self.patterncombo.setEditable(True)
        self.patterncombo.setDuplicatesEnabled(False)

        okcancel = OKCancel()
        self.ok = okcancel.ok
        self.cancel = okcancel.cancel

        self.openfile = QPushButton(QApplication.translate('Text File -> Tag', "&Select File"))
        getclip = QPushButton(QApplication.translate('Text File -> Tag', "&Paste Clipboard"))
        self.connect(getclip, SIGNAL('clicked()'), self.openClipBoard)

        self.hbox.addWidget(self.openfile)
        self.hbox.addWidget(getclip)
        self.hbox.addWidget(self.patterncombo,1)
        self.hbox.addLayout(okcancel)

        self.grid.addLayout(self.hbox,3,0,1,4)
        self.setLayout(self.grid)


        self.connect(self.openfile,SIGNAL("clicked()"),self.openFile)
        self.connect(self.cancel, SIGNAL("clicked()"),self.close)
        self.connect(self.ok, SIGNAL("clicked()"),self.doStuff)

        if clipboard:
            self.openClipBoard()
            return

        self.lastDir = HOMEDIR

        if filename is not None:
            self.openFile(filename)

    def setLines(self):
        self.lines = unicode(self.file.document().toPlainText())
        self.fillTags()

    def openFile(self, filename=None, dirpath=None):
        """Open the file and fills the textboxes."""
        if not dirpath:
            dirpath = self.lastDir

        if not filename:
            filedlg = QFileDialog()
            filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder', dirpath))

        if not filename:
            return True
        try:
            f = open(filename, 'r')
        except (IOError, OSError), detail:
            errormsg = QApplication.translate('Text File -> Tag', "The file <b>%1</b> couldn't be loaded.<br /> Do you want to choose another?")
            ret = QMessageBox.question(self, QApplication.translate('Text File -> Tag', "Error"),
                QApplication.translate('Text File -> Tag', errormsg.arg(filename)),
                QApplication.translate('Text File -> Tag', "&Yes"),
                QApplication.translate('Text File -> Tag', "&No"))
            if ret == 0:
                return self.openFile()
            else:
                return detail

        self.lines = [z.decode('utf8') for z in f.readlines()]
        self.file.setPlainText(u"".join(self.lines))
        self.setLines()
        self.fillTags()
        self.show()
        self.connect(self.file, SIGNAL("textChanged()"), self.setLines)
        self.connect(self.patterncombo, SIGNAL("editTextChanged(QString)"),
            self.fillTags)
        self.lastDir = os.path.dirname(filename)

    def openClipBoard(self):
        text = unicode(QApplication.clipboard().text())
        self.lines = text.split(u'\n')
        self.file.setPlainText(text)
        self.setLines()
        self.fillTags()
        self.show()
        self.connect(self.file, SIGNAL("textChanged()"), self.setLines)
        self.connect(self.patterncombo, SIGNAL("editTextChanged(QString)"),self.fillTags)

    def fillTags(self,string = None): #string is there purely for the SIGNAL
        """Fill the tag textbox."""
        def formattag(tags):
            if tags:
                return "".join(["<b>%s: </b> %s, " % (tag, tags[tag]) for tag in sorted(tags)])[:-2]
            else:
                return ""

        self.dicttags = []
        self.tags.clear()
        for z in self.lines.split("\n"):
            self.dicttags.append(findfunc.filenametotag(unicode(self.patterncombo.currentText()),z,False))
        if self.dicttags:
            self.tags.setHtml("<br/>".join([formattag(z) for z in self.dicttags]))

    def doStuff(self):
        """When I'm done, emit a signal with the updated tags."""
        self.close()
        self.emit(SIGNAL("Newtags"), self.dicttags,
            unicode(self.patterncombo.currentText()))

class EditTag(QDialog):
    """Dialog that allows you to edit the value
    of a tag.

    When the user clicks ok, a 'donewithmyshit' signal
    is emitted containing, three parameters.

    The first being the new tag, the second that tag's
    value and the third is the dictionary of the previous tag.
    (Because the user might choose to edit a different tag,
    then the one that was chosen and you'd want to delete that one)"""
    def __init__(self, tag = None, parent = None, taglist = None, edit=True):

        QDialog.__init__(self, parent)
        self.setWindowTitle(QApplication.translate('Edit Field', 'Edit Field'))
        winsettings('edit_field', self)
        self.vbox = QVBoxLayout()

        label = QLabel(QApplication.translate('Edit Field', "&Field"))
        self.tagcombo = QComboBox()
        self.tagcombo.setEditable(True)
        completer = self.tagcombo.completer()
        completer.setCaseSensitivity(Qt.CaseSensitive)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.tagcombo.setCompleter(completer)
        label.setBuddy(self.tagcombo)
        if not taglist:
            self.tagcombo.addItems(gettaglist())
        else:
            self.tagcombo.addItems(taglist)

        #Get the previous tag
        self.prevtag = tag
        label1 = QLabel(QApplication.translate('Edit Field', "&Value"))
        self.value = QTextEdit()
        label1.setBuddy(self.value)
        okcancel = OKCancel()
        okcancel.ok.setText(QApplication.translate('Edit Field', 'A&dd'))
        if tag is not None:
            x = self.tagcombo.findText(tag[0])

            if x > -1:
                self.tagcombo.setCurrentIndex(x)
            else:
                self.tagcombo.setEditText(tag[0])
            self.value.setPlainText(tag[1])
            if edit:
                okcancel.ok.setText(QApplication.translate('Edit Field', 'E&dit'))

        [self.vbox.addWidget(z) for z in [label, self.tagcombo, label1, self.value]]
        
        self.vbox.addLayout(okcancel)
        self.setLayout(self.vbox)

        self.connect(okcancel, SIGNAL("ok"), self.ok)
        self.connect(okcancel, SIGNAL("cancel"), self.close)

        self.value.selectAll()
        self.tagcombo.lineEdit().selectAll()
        if self.prevtag:
            self.value.setFocus()

    def ok(self):
        self.close()
        self.emit(SIGNAL("donewithmyshit"), unicode(self.tagcombo.currentText()), unicode(self.value.toPlainText()), self.prevtag)

class StatusWidgetItem(QTableWidgetItem):
    def __init__(self, text = None, status = None, colors = None, preview=False):
        QTableWidgetItem.__init__(self)
        self.preview = preview
        self._color = colors
        if text:
            self.setText(text)
        if status and status in self._color:
            self.setBackground(self._color[status])
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
        if status and status in self._color:
            if self._status == ADD and status != REMOVE:
                return
            self.setBackground(self._color[status])
            self._status = status
        else:
            self.setBackground(QTableWidgetItem().background())
            self._status = None

    status = property(_get_status, _set_status)

    def __lt__(self, item):
        if self.text().toUpper() < item.text().toUpper():
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
    def __init__(self, parent = None):
        QHeaderView.__init__(self, Qt.Vertical, parent)
        self.setDefaultSectionSize(self.minimumSectionSize() + 4)
        self.setMinimumSectionSize(1)

        self.connect(self, SIGNAL('sectionResized(int,int,int)'), self._resize)

    def _resize(self, row, oldsize, newsize):
        self.setDefaultSectionSize(newsize)

class ExTags(QDialog):
    """A dialog that shows you the tags in a file

    In addition, the file's image tag is shown."""
    def __init__(self, parent = None, row=None, files=None, preview_mode=False):
        QDialog.__init__(self, parent)
        winsettings('extendedtags', self)
        cparser = PuddleConfig()
        self._taglist = gettaglist()
        self.previewMode = preview_mode

        add = QColor.fromRgb(*cparser.get('extendedtags', 'add', [255,255,0], True))
        edit = QColor.fromRgb(*cparser.get('extendedtags', 'edit', [0,255,0], True))
        remove = QColor.fromRgb(*cparser.get('extendedtags', 'remove', [255,0,0], True))
        self._colors = {ADD:QBrush(add), EDIT:QBrush(edit), REMOVE:QBrush(remove)}

        self.listbox = QTableWidget(0, 2, self)
        self.listbox.setVerticalHeader(VerticalHeader())
        header = self.listbox.horizontalHeader()
        self.listbox.setSortingEnabled(True)
        self.listbox.setSelectionBehavior(QAbstractItemView.SelectRows)
        header.setVisible(True)
        header.setSortIndicatorShown (True)
        header.setStretchLastSection (True)
        header.setSortIndicator (0, Qt.AscendingOrder)
        self.listbox.setHorizontalHeaderLabels([
            QApplication.translate('Extended Tags','Field'),
            QApplication.translate('Extended Tags', 'Value')])

        self.listbox.verticalHeader().setVisible(False)
        self.piclabel = PicWidget(buttons = True)
        self.connect(self.piclabel, SIGNAL('imageChanged'), self._imageChanged)

        if row >= 0 and files:
            buttons = MoveButtons(files, row)
            self.connect(buttons, SIGNAL('indexChanged'), self._prevnext)
            buttons.setVisible(True)
        else:
            buttons = MoveButtons([], row)
            buttons.setVisible(False)
        self._files = files

        self.okcancel = OKCancel()

        self.listbuttons = ListButtons()
        self._reset = QToolButton()
        self._reset.setToolTip(QApplication.translate(
            'Extended Tags',
                'Resets the selected fields to their original value.'))
        self._reset.setIcon(get_icon('edit-undo', ':/undo.png'))
        self.listbuttons.layout().addWidget(self._reset)
        self.connect(self._reset, SIGNAL('clicked()'), self.resetFields)
        self.listbuttons.moveup.hide()
        self.listbuttons.movedown.hide()

        listframe = QFrame()
        listframe.setFrameStyle(QFrame.Box)
        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox,1)
        hbox.addLayout(self.listbuttons, 0)
        listframe.setLayout(hbox)

        imageframe = QFrame()
        imageframe.setFrameStyle(QFrame.Box)
        vbox = QVBoxLayout()
        vbox.setMargin(0)
        vbox.addWidget(self.piclabel)
        vbox.addStretch()
        vbox.addStrut(0)
        imageframe.setLayout(vbox)

        hbox = QHBoxLayout()
        hbox.addWidget(listframe, 1)
        hbox.addSpacing(4)
        hbox.addWidget(imageframe)
        #imageframe.setMaximumWidth(270)
        hbox.addStrut(1)

        layout = QVBoxLayout()
        layout.addLayout(hbox)
        layout.addLayout(self.okcancel)
        self.okcancel.insertWidget(0, buttons)
        self.setLayout(layout)

        self.connect(self.okcancel, SIGNAL("cancel"), self.closeMe)
        self.connect(self.listbox,
            SIGNAL("itemDoubleClicked(QTableWidgetItem *)"), self.editTag)
        self.connect(self.listbox,
            SIGNAL("itemSelectionChanged()"), self._checkListBox)
        self.connect(self.okcancel, SIGNAL("ok"),self.OK)
        
        clicked = SIGNAL('clicked()')
        self.connect(self.listbuttons, SIGNAL('edit'), self.editTag)
        self.connect(self.listbuttons.add, clicked, self.addTag)
        self.connect(self.listbuttons.remove, clicked, self.removeTag)
        self.connect(self.listbuttons, SIGNAL('duplicate'), self.duplicate)

        self.setMinimumSize(450,350)

        self.canceled = False
        self.filechanged = False

        if row >= 0 and files:
            self._prevnext(row)
        else:
            self.loadFiles(files)

    def addTag(self):
        win = EditTag(parent=self, taglist=self._taglist)
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.editTagBuddy)
    
    def closeEvent(self,event):
        self.piclabel.close()
        QDialog.closeEvent(self,event)

    def closeMe(self):
        self.canceled = True
        self.close()

    def _deletePressed(self, item):
        if self.listbox.deletePressed:
            self.listbox.deletePressed = False
            self.removeTag()

    def _checkListBox(self):
        if self.listbox.rowCount() <= 0:
            self.listbox.setEnabled(False)
            self.listbuttons.edit.setEnabled(False)
            self.listbuttons.remove.setEnabled(False)
            self.listbuttons.duplicate.setEnabled(False)
            self._reset.setEnabled(False)
        else:
            self.listbox.setEnabled(True)
            self._reset.setEnabled(True)
            if len(self.listbox.selectedItems()) / 2 > 1:
                self.listbuttons.edit.setEnabled(False)
                self.listbuttons.duplicate.setEnabled(False)
            else:
                self.listbuttons.edit.setEnabled(True)
                self.listbuttons.remove.setEnabled(True)
                self.listbuttons.duplicate.setEnabled(True)
            

    def _imageChanged(self):
        self.filechanged = True

    def duplicate(self):
        self.editTag(True)

    def editTag(self, duplicate=False):
        """Opens a windows that allows the user
        to edit the tag in item(a QListWidgetItem that's supposed to
        be from self.listbox).

        If item is None then the currently selected item
        in self.listbox is used.

        After the value is edited, self.listbox is updated."""
        row = self.listbox.currentRow()
        if row != -1:
            prevtag = self._tag(row)
            if duplicate is True:
                win = EditTag(prevtag, self, self._taglist, edit=False)
            else:
                win = EditTag(prevtag, self, self._taglist)
            win.setModal(True)
            win.show()
            if duplicate is True: #Have to check for truth, because this method
                                  #is called by the doubleclicked signal.
                buddy = partial(self.editTagBuddy, duplicate=True)
            else:
                buddy = self.editTagBuddy
            self.connect(win, SIGNAL("donewithmyshit"), buddy)


    def editTagBuddy(self, tag, value, prevtag = None, duplicate=False):
        item = self.listbox.item
        rowcount = self.listbox.rowCount()
        if prevtag is not None:
            if duplicate:
                row = rowcount
                self._settag(rowcount, tag, value, ADD, self.previewMode, True)
            else:
                if tag == prevtag[0]:
                    row = self.listbox.currentRow()
                    self._settag(row, tag, value, EDIT, self.previewMode, True)
                    if row +1< rowcount:
                        self.listbox.selectRow(row + 1)
                else:
                    cur_item = self.listbox.currentItem()
                    self.resetFields([cur_item])
                    self.listbox.setCurrentItem(cur_item,
                        QItemSelectionModel.ClearAndSelect)
                    self.listbox.selectRow(self.listbox.row(cur_item))
                    self.removeTag()                    
                    valitem = self._settag(rowcount, tag,
                        value, ADD, self.previewMode, True)
                    cur_item.linked = [valitem]
        else:
            self._settag(rowcount, tag, value, ADD, self.previewMode, True)
        self._checkListBox()
        self.filechanged = True
        self.listbox.clearSelection()

    def listtotag(self):
        gettag = self._tag
        tags = {}
        lowered = {}
        listitems = [gettag(row, True) for row
            in xrange(self.listbox.rowCount())]

        for field, val, status in listitems:
            if status != REMOVE:
                if val == u'<keep>':
                    continue
                l_field = field.lower()
                if l_field in lowered:
                    tags[lowered[l_field]].append(val)
                else:
                    lowered[l_field] = field
                    tags[field] = [val]
            else:
                if field.lower() not in lowered:
                    tags[field] = []
                    lowered[l_field] = field
        return tags

    def loadFiles(self, audios):
        if self.filechanged:
            self.save()
        self.filechanged = False
        self.listbox.clearContents()
        self.listbox.setRowCount(0)
        self.piclabel.lastfilename = audios[0].dirpath
        self.piclabel.setEnabled(False)
        self.piclabel.setImages(None)
        if len(audios) == 1:
            audio = audios[0]
            self.setWindowTitle(audios[0].filepath)
            self._loadsingle(audio)
        else:
            self.setWindowTitle(QApplication.translate('Extended Tags', 'Different files.'))
            common, numvalues, imagetags = commontags(audios)
            images = common['__image']
            del(common['__image'])
            previews = set(audios[0].preview)
            italics = set(audios[0].equal_fields())
            for audio in audios[1:]:
                previews = previews.intersection(audio.preview)
                italics = italics.intersection(audio.equal_fields())
            row = 0
            for field, values in common.iteritems():
                if field in italics:
                    preview = UNCHANGED
                elif field in previews:
                    preview = BOLD
                else:
                    preview = UNCHANGED
                if numvalues[field] != len(audios):
                    self._settag(row, field, '<keep>')
                    row += 1
                else:
                    if isinstance(values, basestring):
                        self._settag(row, field, values, None, preview)
                        row += 1
                    else:
                        for v in values:
                            self._settag(row, field, v, None, preview)
                            row += 1
            if images:
                self.piclabel.setImageTags(imagetags)
                self.piclabel.setEnabled(True)
                self.piclabel.setImages(images)
            else:
                self.piclabel.setImageTags(imagetags)
                self.piclabel.setImages(None)
                self.piclabel.setEnabled(True)
                if images == 0:
                    self.piclabel.context = 'Cover Varies'
        self._checkListBox()

    def _loadsingle(self, tags):
        items = []
        d = tags.usertags.copy()
        italics = tags.equal_fields()
        
        for key, val in sorted(d.items()):
            if key in italics:
                preview = UNCHANGED
            elif key in tags.preview:
                preview = BOLD
            else:
                preview = UNCHANGED
            if isinstance(val, basestring):
                items.append([key, val, None, preview])
            else:
                [items.append([key, z, None, preview]) for z in val]
        [self._settag(i, *item) for i, item in enumerate(items)]
        self.piclabel.lastfilename = tags.dirpath
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

    def OK(self):
        self.save()
        self.close()

    def _prevnext(self, row):
        if self.filechanged:
            self.save()
        self.loadFiles([self._files[row]])

    def removeTag(self):
        l = self.listbox
        l.setSortingEnabled(False)
        to_remove = {}
        rows = []
        for i in self.listbox.selectedItems():
            row = l.row(i)
            if i.status == ADD:
                to_remove[row] = i
            rows.append(row)
            i.status = REMOVE
            i.status = REMOVE
        [l.removeRow(l.row(z)) for z in to_remove.values()]
        l.setSortingEnabled(True)
        self.filechanged = True
        self._checkListBox()
        if rows:
            row = max(rows)
            self.listbox.clearSelection()
            if row + 1 < self.listbox.rowCount():
                self.listbox.selectRow(row + 1)

    def resetFields(self, items=None):
        box = self.listbox
        to_remove = {} #Stores row: item values so that only one item
                       #gets removed per row.
        if items is None:
            items = box.selectedItems()

        max_row = -1
        for item in box.selectedItems():
            for i in item.linked:
                try:
                    to_remove[box.row(i)] = i
                except RuntimeError:
                    pass
            item.reset()
            row = self.listbox.row(item)
            if row > max_row:
                max_row = row
            if item.status == REMOVE:
                to_remove[row] = item

        self.listbox.clearSelection()
        if max_row != -1 and max_row + 1 < self.listbox.rowCount():
            self.listbox.selectRow(max_row + 1)

        for item in to_remove.values():
            self.listbox.removeRow(self.listbox.row(item))
        self._checkListBox()
        

    def save(self):
        if not self.filechanged:
            return
        tags = self.listtotag()
        if self.piclabel.context != u'Cover Varies':
            if not self.piclabel.images:
                tags['__image'] = []
            else:
                tags["__image"] = self.piclabel.images
        newtags = [z for z in tags if z not in self._taglist]
        if newtags and newtags != ['__image']:
            settaglist(newtags + self._taglist)
        self.emit(SIGNAL('extendedtags'), tags)

    def _settag(self, row, tag, value, status=None, preview=False, check=False):
        l = self.listbox
        l.setSortingEnabled(False)
        if row >= l.rowCount():
            l.insertRow(row)
            tagitem = StatusWidgetItem(tag, status, self._colors, preview)
            l.setItem(row, 0, tagitem)
            valitem = StatusWidgetItem(value, status, self._colors, preview)
            l.setItem(row, 1, valitem)
        else:
            tagitem = l.item(row, 0)
            tagitem.setText(tag)
            tagitem.status = status

            valitem = l.item(row, 1)
            valitem.setText(value)
            valitem.status = status

        if check:
            lowered_tag = tag.lower()
            for row in xrange(l.rowCount()):
                item = l.item(row, 0)
                text = unicode(item.text())
                if text != tag and text.lower() == lowered_tag:
                    item.setText(tag)
                    if item.status not in [ADD, REMOVE]:
                        item.status = EDIT
                        l.item(row, 1).status = EDIT

        l.setSortingEnabled(True)
        return valitem

    def _tag(self, row, status = None):
        getitem = self.listbox.item
        item = getitem(row, 0)
        tag = unicode(item.text())
        value = unicode(getitem(row, 1).text())
        if status:
            return (tag, value, item.status)
        else:
            return (tag, value)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    wid = ImportWindow(clipboard = True)
    wid.resize(200,400)
    wid.show()
    app.exec_()
