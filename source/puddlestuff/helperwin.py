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
                            PicWidget, winsettings, PuddleConfig)
from copy import deepcopy
ADD, EDIT, REMOVE = (1,2,3)
from puddlestuff.audioinfo import commontags, INFOTAGS, REVTAGS

class TrackWindow(QDialog):
    """Dialog that allows automatic numbering of tracks.
    Number the tracks in range(start, end)

    Emit's the signal 'newtracks' containing a list of two items when it's closed:
    the from value and the to value(a unicode string). If no to value
    was specified then the to value is an empty string ('')"""
    def __init__(self, parent=None, minval=0, numtracks = None, enablenumtracks = False):
        QDialog.__init__(self,parent)
        self.setWindowTitle("Autonumbering Wizard")
        winsettings('autonumbering', self)

        self.hboxlayout = QHBoxLayout()
        self.hboxlayout.setMargin(0)
        self.hboxlayout.setSpacing(6)

        self.label = QLabel("Start")
        self.hboxlayout.addWidget(self.label)

        self.frombox = QSpinBox()
        self.frombox.setValue(minval)
        self.frombox.setMaximum(65536)
        self.hboxlayout.addWidget(self.frombox)
        self.hboxlayout.addStretch()

        self.hboxlayout2 = QHBoxLayout()
        self.checkbox = QCheckBox("Add track seperator ['/']")
        self.numtracks = QLineEdit()
        self.numtracks.setEnabled(False)
        self.numtracks.setMaximumWidth(50)
        self.foldernumbers = QCheckBox("Restart numbering at each directory.")

        self.hboxlayout2.addWidget(self.checkbox)
        self.hboxlayout2.addWidget(self.numtracks)
        self.hboxlayout2.addStretch()
        self.hboxlayout3 = QHBoxLayout()
        okcancel = OKCancel()

        self.vbox = QVBoxLayout(self)
        self.vbox.addLayout(self.hboxlayout)
        self.vbox.addLayout(self.hboxlayout2)
        self.vbox.addWidget(self.foldernumbers)
        self.vbox.addLayout(okcancel)


        self.setLayout(self.vbox)
        self.connect(okcancel,SIGNAL('ok'), self.doStuff)
        self.connect(okcancel,SIGNAL('cancel'),self.close)
        self.connect(self.checkbox, SIGNAL("stateChanged(int)"), self.setEdit)
        self.numtracks.setText(unicode(numtracks))

        if enablenumtracks:
            self.checkbox.setCheckState(Qt.Checked)
        else:
            self.checkbox.setCheckState(Qt.Unchecked)

    def setEdit(self, val):
        #print val
        if val == 2:
            self.numtracks.setEnabled(True)
        else:
            self.numtracks.setEnabled(False)

    def doStuff(self):
        self.close()
        if self.checkbox.checkState() == 2:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), unicode(self.numtracks.text()), self.foldernumbers.checkState()])
        else:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), "", self.foldernumbers.checkState()])


class ImportWindow(QDialog):
    """Dialog that allows you to import a file to tags.

    emits a signal newtags with a dictionary containing
    the...new tags."""
    def __init__(self,parent = None, filename = None, clipboard = None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("Import tags from file")
        winsettings('importwin', self)

        self.grid = QGridLayout()

        self.label = QLabel("File")
        self.grid.addWidget(self.label,0,0)

        self.label = QLabel("Tags")
        self.grid.addWidget(self.label,0,2)


        self.file = QTextEdit()
        self.grid.addWidget(self.file,1,0,1,2)

        self.tags = QTextEdit()
        self.grid.addWidget(self.tags,1,2,1,2)
        self.tags.setLineWrapMode(QTextEdit.NoWrap)

        self.label = QLabel("Pattern")
        self.grid.addWidget(self.label,2,0,)

        self.hbox = QHBoxLayout()

        self.patterncombo = QComboBox()
        self.patterncombo.setEditable(True)
        self.patterncombo.setDuplicatesEnabled(False)

        self.ok = QPushButton("&OK")
        self.cancel = QPushButton("&Cancel")

        self.openfile = QPushButton("&Select File")
        getclip = QPushButton("&Paste Clipboard")
        self.connect(getclip, SIGNAL('clicked()'), self.openClipBoard)

        self.hbox.addWidget(self.openfile)
        self.hbox.addWidget(getclip)
        self.hbox.addWidget(self.patterncombo,1)
        self.hbox.addWidget(self.ok)
        self.hbox.addWidget(self.cancel)

        self.grid.addLayout(self.hbox,3,0,1,4)
        self.setLayout(self.grid)


        self.connect(self.openfile,SIGNAL("clicked()"),self.openFile)
        self.connect(self.cancel, SIGNAL("clicked()"),self.close)
        self.connect(self.ok, SIGNAL("clicked()"),self.doStuff)

        if clipboard:
            self.openClipBoard()
            return

        if filename is not None:
            self.openFile(filename)


    def setLines(self):
        self.lines = unicode(self.file.document().toPlainText())
        self.fillTags()

    def openFile(self, filename = ""):
        """Open the file and fills the textboxes."""
        if not filename:
            filedlg = QFileDialog()
            filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder',QDir.homePath()))
        if filename != "":
            try:
                f = open(filename)
            except (IOError, OSError), detail:
                ret = QMessageBox.question(self, "Error", u"I couldn't load the file:" + \
                    "<b>%s</b> <br /> . Do you want to choose another?" % filename,
                        "&Yes, choose another", "&No, close this window.")
                if ret == 0:
                    self.openFile()
                else:
                    self.close()
                return

            self.lines = f.readlines()
            self.file.setPlainText("".join(self.lines))
            self.setLines()
            self.fillTags()
            self.show()
            self.connect(self.file, SIGNAL("textChanged()"), self.setLines)
            self.connect(self.patterncombo, SIGNAL("editTextChanged(QString)"),self.fillTags)

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
        for z in self.lines.split("\n"):
            self.dicttags.append(findfunc.filenametotag(unicode(self.patterncombo.currentText()),z,False))
        if self.dicttags:
            self.tags.setHtml("<br/>".join([formattag(z) for z in self.dicttags]))

    def doStuff(self):
        """When I'm done, emit a signal with the updated tags."""
        self.close()
        self.emit(SIGNAL("Newtags"), self.dicttags)

class EditTag(QDialog):
    """Dialog that allows you to edit the value
    of a tag.

    When the user clicks ok, a 'donewithmyshit' signal
    is emitted containing, three parameters.

    The first being the new tag, the second that tag's
    value and the third is the dictionary of the previous tag.
    (Because the user might choose to edit a different tag,
    then the one that was chosen and you'd want to delete that one)"""
    def __init__(self, tag = None, parent = None, taglist = None):

        QDialog.__init__(self, parent)
        self.vbox = QVBoxLayout()

        label = QLabel("Tag")
        self.tagcombo = QComboBox()
        self.tagcombo.setEditable(True)
        if not taglist:
            self.tagcombo.addItems(gettaglist())
        else:
            self.tagcombo.addItems(taglist)

        #Get the previous tag
        self.prevtag = tag
        label1 = QLabel("Value")
        self.value = QTextEdit()

        if tag is not None:
            x = self.tagcombo.findText(tag[0])

            if x > -1:
                self.tagcombo.setCurrentIndex(x)
            else:
                self.tagcombo.setEditText(tag[0])
            self.value.setPlainText(tag[1])

        [self.vbox.addWidget(z) for z in [label, self.tagcombo, label1, self.value]]
        okcancel = OKCancel()
        okcancel.ok.setText("&Save")
        self.vbox.addLayout(okcancel)
        self.setLayout(self.vbox)

        self.connect(okcancel, SIGNAL("ok"), self.ok)
        self.connect(okcancel, SIGNAL("cancel"), self.close)

    def ok(self):
        self.close()
        self.emit(SIGNAL("donewithmyshit"), unicode(self.tagcombo.currentText()), unicode(self.value.toPlainText()), self.prevtag)

class StatusWidgetItem(QTableWidgetItem):
    def __init__(self, text = None, status = None, colors = None):
        QTableWidgetItem.__init__(self)
        self._color = colors
        if text:
            self.setText(text)
        if status and status in self._color:
            self.setBackground(self._color[status])
        self._status = status
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

    def _getstatus(self):
        return self._status

    def _setstatus(self, status):
        if status and status in self._color:
            self.setBackground(self._color[status])
            self._status = status
        else:
            self.setBackground(QTableWidgetItem().background())
            self._status = None

    status = property(_getstatus, _setstatus)


class ExTags(QDialog):
    """A dialog that shows you the tags in a file

    In addition, the file's image tag is shown."""
    def __init__(self, parent = None, row = None, model = None):
        """model -> is a puddlestuff.TableModel object
        row -> the row that contains the file to be displayed
        """
        QDialog.__init__(self, parent)
        winsettings('extendedtags', self)
        cparser = PuddleConfig()
        self._taglist = gettaglist()

        add = QColor.fromRgb(*cparser.get('extendedtags', 'add', [255,0,0], True))
        edit = QColor.fromRgb(*cparser.get('extendedtags', 'edit', [0,255,0], True))
        remove = QColor.fromRgb(*cparser.get('extendedtags', 'remove', [0,0,255], True))
        self._colors = {ADD:QBrush(add), EDIT:QBrush(edit), REMOVE:QBrush(remove)}

        self.listbox = QTableWidget(0, 2, self)
        header = self.listbox.horizontalHeader()
        self.listbox.setSortingEnabled(True)
        self.listbox.setSelectionBehavior(QAbstractItemView.SelectRows)
        header.setVisible(True)
        header.setSortIndicatorShown (True)
        header.setStretchLastSection (True)
        header.setSortIndicator (0, Qt.AscendingOrder)
        self.listbox.setHorizontalHeaderLabels(['Tag', 'Value'])

        self.listbox.verticalHeader().setVisible(False)
        self.piclabel = PicWidget(buttons = True)
        self.connect(self.piclabel, SIGNAL('imageChanged'), self._imageChanged)

        if row >= 0 and model:
            buttons = MoveButtons(model.taginfo, row)
            self.connect(buttons, SIGNAL('indexChanged'), self._prevnext)
            self._model = model
            buttons.setVisible(True)
        else:
            buttons = MoveButtons([], row)
            buttons.setVisible(False)

        self.okcancel = OKCancel()

        self.listbuttons = ListButtons()
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
        imageframe.setLayout(vbox)

        hbox = QHBoxLayout()
        hbox.addWidget(listframe, 1)
        hbox.addSpacing(4)
        hbox.addWidget(imageframe, 0)

        layout = QVBoxLayout()
        layout.addLayout(hbox)
        layout.addLayout(self.okcancel)
        self.okcancel.insertWidget(0, buttons)
        self.setLayout(layout)

        self.connect(self.okcancel, SIGNAL("cancel"), self.closeMe)
        self.connect(self.listbox, SIGNAL("itemDoubleClicked(QTableWidgetItem *)"), self.editTag)
        self.connect(self.okcancel, SIGNAL("ok"),self.OK)

        clicked = SIGNAL('clicked()')
        self.connect(self.listbuttons.edit, clicked, self.editTag)
        self.connect(self.listbuttons.add, clicked, self.addTag)
        self.connect(self.listbuttons.remove, clicked, self.removeTag)

        self.setMinimumSize(450,350)

        self.canceled = False
        self.filechanged = False

        if row >= 0 and model:
            self._prevnext(row)

    def _prevnext(self, row):
        if self.filechanged:
            self.save()
        self.loadFiles([self._model.taginfo[row]])

    def _checkListBox(self):
        if self.listbox.rowCount() <= 0:
            self.listbox.setEnabled(False)
            self.listbuttons.edit.setEnabled(False)
            self.listbuttons.remove.setEnabled(False)
        else:
            self.listbox.setEnabled(True)
            self.listbuttons.edit.setEnabled(True)
            self.listbuttons.remove.setEnabled(True)

    def _imageChanged(self):
        self.filechanged = True

    def removeTag(self):
        l = self.listbox
        row = l.currentRow()
        l.setSortingEnabled(False)
        for i in self.listbox.selectedItems():
            row = l.row(i)
            i.status = REMOVE
            i.status = REMOVE
        l.setSortingEnabled(True)
        self.filechanged = True
        self._checkListBox()

    def closeMe(self):
        self.canceled = True
        self.close()

    def closeEvent(self,event):
        self.piclabel.close()
        QDialog.closeEvent(self,event)

    def save(self):
        if not self.filechanged:
            return
        tags = self.listtotag()
        if not self.piclabel.images:
            tags['__image'] = []
        else:
            tags["__image"] = self.piclabel.images
        newtags = [z for z in tags if z not in self._taglist]
        if newtags and newtags != ['__image']:
            settaglist(newtags + self._taglist)
        self.emit(SIGNAL('extendedtags'), tags)

    def OK(self):
        self.save()
        self.close()

    def addTag(self):
        win = EditTag(parent = self, taglist = self._taglist)
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.editTagBuddy)

    def _tag(self, row, status = None):
        getitem = self.listbox.item
        item = getitem(row, 0)
        tag = unicode(item.text())
        value = unicode(getitem(row, 1).text())
        if status:
            return (tag, value, item.status)
        else:
            return (tag, value)

    def _settag(self, row, tag, value, status = None):
        l = self.listbox
        l.setSortingEnabled(False)
        if row >= l.rowCount():
            l.insertRow(row)
        else:
            if l.item(row, 0).status:
                status = l.item(row, 0).status
        tagitem = StatusWidgetItem(tag, status, self._colors)
        l.setItem(row, 0, tagitem)
        valitem = StatusWidgetItem(value, status, self._colors)
        l.setItem(row, 1, valitem)
        l.setSortingEnabled(True)

    def editTag(self):
        """Opens a windows that allows the user
        to edit the tag in item(a QListWidgetItem that's supposed to
        be from self.listbox).

        If item is None then the currently selected item
        in self.listbox is used.

        After the value is edited, self.listbox is updated."""
        row = self.listbox.currentRow()
        if row != -1:
            prevtag = self._tag(row)
            win = EditTag(prevtag, self, self._taglist)
            win.setModal(True)
            win.show()
            self.connect(win, SIGNAL("donewithmyshit"), self.editTagBuddy)


    def editTagBuddy(self, tag, value, prevtag = None):
        if prevtag is not None:
            self._settag(self.listbox.currentRow(), tag, value, EDIT)
        else:
            self._settag(self.listbox.rowCount(), tag, value, ADD)
        self._checkListBox()
        self.filechanged = True

    def listtotag(self):
        gettag = self._tag
        tags = {}
        listitems = [gettag(row, True) for row in xrange(self.listbox.rowCount())]
        try:
            for tag, val, status in listitems:
                if status != REMOVE:
                    if val == u'<keep>':
                        continue
                    if tag in tags:
                        tags[tag].append(val)
                    else:
                        tags[tag] = [val]
                else:
                    if tag not in tags:
                        tags[tag] = []
        except Exception, e:
            print listitems
            raise e
        return tags

    def loadFiles(self, audios):
        if self.filechanged:
            self.save()
        self.filechanged = False
        self.listbox.clearContents()
        self.listbox.setRowCount(0)
        self.piclabel.lastfilename = audios[0]['__folder']
        self.piclabel.setEnabled(False)
        self.piclabel.setImages(None)
        if len(audios) == 1:
            audio = audios[0]
            self.setWindowTitle(audios[0]["__filename"])
            self._loadsingle(audio)
        else:
            self.setWindowTitle('Different files.')
            common, numvalues, imagetags = commontags(audios)
            images = common['__image']
            del(common['__image'])
            for i, key in enumerate(common):
                if numvalues[key] != len(audios):
                    self._settag(i, key, '<keep>')
                else:
                    self._settag(i, key, common[key])
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
        for item, val in sorted(tags.usertags.items()):
            [items.append([item, z]) for z in val]
        [self._settag(i, *item) for i, item in enumerate(items)]
        self.piclabel.lastfilename = tags['__folder']
        if '__library' not in tags:
            self.piclabel.setImageTags(tags.IMAGETAGS)
            if tags.IMAGETAGS:
                self.piclabel.setEnabled(True)
                if tags.images:
                    self.piclabel.setImages(deepcopy(tags.images))
                else:
                    self.piclabel.setImages(None)
        self._checkListBox()
        self.setWindowTitle(tags["__filename"])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    wid = ImportWindow()
    wid.resize(200,400)
    wid.show()
    app.exec_()
