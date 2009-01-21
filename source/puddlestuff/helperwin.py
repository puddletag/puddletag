"""Dialog's that crop up along the application, but are used at at most
one place, and aren't that complicated are put here."""

"""helperwin.py

Copyright (C) 2008 concentricpuddle

This file is part of puddletag, a semi-good music tag editor.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys, findfunc, audioinfo, os,pdb
from puddleobjects import OKCancel, partial
from mutagen.id3 import APIC
from copy import deepcopy

class TrackWindow(QDialog):
    """Dialog that allows automatic numbering of tracks.
    Number the tracks in range(start, end)

    Emit's the signal 'newtracks' containing a list of two items when it's closed:
    the from value and the to value(a unicode string). If no to value
    was specified then the to value is an empty string ('')"""
    def __init__(self, parent=None, minval=0, numtracks = None, enablenumtracks = False):
        QDialog.__init__(self,parent)
        self.setWindowTitle("Autonumbering Wizard")

        self.hboxlayout = QHBoxLayout()
        self.hboxlayout.setMargin(0)
        self.hboxlayout.setSpacing(6)

        self.label = QLabel("Start")
        self.hboxlayout.addWidget(self.label)

        self.frombox = QSpinBox()
        self.frombox.setValue(minval)
        self.frombox.setMaximum(65536)
        self.hboxlayout.addWidget(self.frombox)

        self.hboxlayout2 = QHBoxLayout()
        self.checkbox = QCheckBox("Add track seperator ['/']")
        self.numtracks = QLineEdit()
        self.numtracks.setEnabled(False)
        self.numtracks.setMaximumWidth(50)
        self.foldernumbers = QCheckBox("Restart numbering at each directory.")

        self.hboxlayout2.addWidget(self.checkbox)
        self.hboxlayout2.addWidget(self.numtracks)

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
    def __init__(self,parent = None, filename = None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("Import tags from file")

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

        self.hbox.addWidget(self.openfile)
        self.hbox.addWidget(self.patterncombo,1)
        self.hbox.addWidget(self.ok)
        self.hbox.addWidget(self.cancel)

        self.grid.addLayout(self.hbox,3,0,1,4)
        self.setLayout(self.grid)


        self.connect(self.openfile,SIGNAL("clicked()"),self.openFile)
        self.connect(self.cancel, SIGNAL("clicked()"),self.close)
        self.connect(self.ok, SIGNAL("clicked()"),self.doStuff)

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
                ret = QMessageBox.question(self, "Error", u"I could load the file:" + \
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


class Label(QLabel):
    """Just a QLabel that sends a clicked() signal
    when left-clicked."""
    def __init__ (self, text = "", parent = None):
        QLabel.__init__ (self, text, parent)

    def mouseReleaseEvent(self, event):
      if event.button() == Qt.LeftButton:
        self.emit(SIGNAL("clicked()"))
      QLabel.mousePressEvent(self, event)

class PicWidget(QWidget):
    """A with that shows a files pictures.

    images is a list of mutagen.id3.APIC objects.
    It allows the user to edit, save and delete whichever
    picture the user wants, by right-clicking on it.

    In addition, there are buttons to browse through
    all the pictures.

    Some important attributes are:
    currentImage -> The index of the current image
    maxImage -> Shows the current image fullsized.
    setImages -> Guess
    addImage -> Guess again...but it also shows and open file dialog.
    removeImage -> Removes the current image.
    next and prevImage -> Moves to the next and previous image.
    saveToFile -> Save the current image to file."""
    def __init__ (self, images = None, parent = None):
        QWidget.__init__(self, parent)
        self.label = Label()
        self.label.setFrameStyle(QFrame.Box)
        self.label.setMinimumSize(180,150)
        self.label.setMaximumSize(180, 150)
        self.label.setAlignment(Qt.AlignCenter)

        self.next = QPushButton('&>>')
        self.prev = QPushButton('&<<')
        self.connect(self.next, SIGNAL('clicked()'), self.nextImage)
        self.connect(self.prev, SIGNAL('clicked()'), self.prevImage)
        self.connect(self.label, SIGNAL('clicked()'), self.maxImage)

        vbox = QVBoxLayout()
        vbox.addStretch()
        vbox.addWidget(self.next,0)
        vbox.addWidget(self.prev,0)
        vbox.addStretch()

        self.label.setContextMenuPolicy(Qt.ActionsContextMenu)

        self.savepic = QAction("&Save picture", self)
        self.label.addAction(self.savepic)
        self.connect(self.savepic, SIGNAL("triggered()"), self.saveToFile)

        self.addpic = QAction("&Add picture", self)
        self.label.addAction(self.addpic)
        self.connect(self.addpic, SIGNAL("triggered()"), self.addImage)

        self.removepic = QAction("&Remove picture", self)
        self.label.addAction(self.removepic)
        self.connect(self.removepic, SIGNAL("triggered()"), self.removeImage)

        self.editpic = QAction("&Change picture", self)
        self.label.addAction(self.editpic)
        self.edit = partial(self.addImage, True)
        self.connect(self.editpic, SIGNAL("triggered()"), self.edit)

        hbox = QHBoxLayout()
        hbox.addWidget(self.label)
        hbox.addLayout(vbox)
        self.setLayout(hbox)
        self.win = PicWin(parent = self)
        self._currentImage = -1
        self.images = []
        self.next.setEnabled(False)
        self.prev.setEnabled(False)
        if images:
            self.setImages(images)

    def close(self):
        self.win.close()
        QWidget.close(self)

    def _setImage(self, num):
        try:
            image = QImage().fromData(self.images[num].data)
        except IndexError:
            self.label.setPixmap(QPixmap())
            return

        self.pixmap = QPixmap.fromImage(image)
        self.label.setPixmap(self.pixmap.scaled(self.label.size(), Qt.KeepAspectRatio))
        self._currentImage = num
        self.label.setFrameStyle(QFrame.NoFrame)

        self.next.setEnabled(True)
        self.prev.setEnabled(True)
        if num >= len(self.images) - 1:
            self.next.setEnabled(False)
        if num <= 0:
            self.prev.setEnabled(False)

    def _getImage(self):
        return self._currentImage

    currentImage = property(_getImage, _setImage,"""The index of the currently
    selected image. It can be set to some valid index too. If the index isn't valid
    then a blank image is loaded.""")

    def maxImage(self):
        if self.pixmap:
            if self.win.isVisible():
                self.win.hide()
            else:
                self.win = PicWin(self.pixmap, self)
                self.win.show()

    def setImages(self, images):
        if images:
            self.images = images
            self.currentImage = 0
        else:
            self.label.setFrameStyle(QFrame.Box)
            self.label.setPixmap(QPixmap())
            self.pixmap = None
            self.images = None

    def nextImage(self):
        self.currentImage += 1

    def prevImage(self):
        self.currentImage -= 1

    def saveToFile(self):
        """Opens a dialog that allows the user to save,
        the image in the current file to disk."""
        if self.currentImage > -1:
            filedlg = QFileDialog()
            filename = unicode(filedlg.getSaveFileName(self,
                    'Save as...',"~", "PNG (*.png)"))
            if os.path.exists(os.path.dirname(filename)):
                self.pixmap.save(filename, "PNG")

    def addImage(self, edit = False):
        filedlg = QFileDialog()
        filename = unicode(filedlg.getOpenFileName(self,
                'Save as...',"~", "JPEG Images (*.jpg);;PNG Images (*.png);;All Files(*.*)"))
        image = QImage()
        if image.load(filename):
            ba = QByteArray()
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            image.save(buf, "PNG")
            data = buf.data()
            if edit and self.images:
                    desc = self.images[self.currentImage].desc
                    pic = APIC(3,'image/png', 3, desc, data)
                    self.images[self.currentImage] = pic
                    self.currentImage = self.currentImage
            else:
                (text, ret) = QInputDialog.getText(self,"Input text", "Please enter a short description for the picture.",
                                    QLineEdit.Normal, u'' + unicode(self.currentImage))
                if not ret:
                        text = u'Picture' + unicode(self.currentImage)
                pic = APIC(3,'image/png', 3, text, data)
                if not self.images:
                    self.setImages([pic])
                else:
                    self.images.append(pic)
                    self.currentImage = len(self.images) - 1

    def removeImage(self):
        if len(self.images) >= 1:
            del(self.images[self.currentImage])
            if self.currentImage >= len(self.images) - 1 and self.currentImage > 0:
                self.currentImage = len(self.images) - 1
            else:
                self.currentImage =  self.currentImage


class PicWin(QDialog):
    """A windows that shows an image."""
    def __init__(self, pixmap = None, parent = None):
        """Loads the image specified in QPixmap pixmap.
        If picture is clicked, the window closes.

        If you don't want to load an image when the class
        is created, let pixmap = None and call setImage later."""
        QDialog.__init__(self, parent)
        self.label = Label()

        vbox = QVBoxLayout()
        vbox.addWidget(self.label)
        self.setLayout(vbox)

        if pixmap is not None:
            self.setImage(pixmap)

        self.connect(self.label, SIGNAL('clicked()'), self.close)

    def setImage(self, pixmap):
        self.label.setPixmap(pixmap)
        self.setMaximumSize(pixmap.size())
        self.setMinimumSize(pixmap.size())


class EditTag(QDialog):
    """Dialog that allows you to edit the value
    of a tag.

    When the user clicks ok, a 'donewithmyshit' signal
    is emitted containing, three parameters.

    The first being the new tag, the second that tag's
    value and the third is the dictionary of the previous tag.
    (Because the user might choose to edit a different tag,
    then the one that was chosen and you'd want to delete that one)"""
    def __init__(self, tag = None, parent = None):

        QDialog.__init__(self, parent)
        self.vbox = QVBoxLayout()

        label = QLabel("Tag")
        self.tagcombo = QComboBox()
        self.tagcombo.setEditable(True)
        self.tagcombo.addItems(sorted([z for z in audioinfo.REVTAGS]))

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

class ExTags(QDialog):
    """A dialog that shows you the tags in a file

    In addition, the file's image tag is shown."""
    def __init__(self, model = None, row = 0, parent = None):
        """model -> is a puddlestuff.TableModel object
        row -> the row that contains the file to be displayed
        """
        QDialog.__init__(self, parent)
        self.listbox = QListWidget()
        self.piclabel = PicWidget()

        if type(model) is not str:
            self.model = model
            self.loadFile(row)

        addtag = QPushButton('&Add')
        edittag = QPushButton('&Edit')
        removetag = QPushButton('&Remove')

        self.okcancel = OKCancel()

        vbox = QVBoxLayout()
        vbox.addWidget(self.piclabel)
        (h1, h2, h3) = (QHBoxLayout(),QHBoxLayout(),QHBoxLayout())
        for widget, box in zip((addtag, edittag, removetag),(h1, h2, h3)):
            box.addWidget(widget)
            box.addStretch()
            vbox.addLayout(box)
        vbox.addStretch()

        self.hbox = QHBoxLayout()
        self.hbox.addWidget(self.listbox,1)
        self.hbox.addLayout(vbox,0)

        self.vbox = QVBoxLayout()
        self.vbox.addLayout(self.hbox)
        prevaudio = QPushButton('<<')
        nextaudio = QPushButton('>>')
        self.okcancel.insertWidget(1, nextaudio)
        self.okcancel.insertWidget(1, prevaudio)
        self.vbox.addLayout(self.okcancel)
        self.setLayout(self.vbox)


        self.connect(self.okcancel, SIGNAL("cancel"), self.closeMe)
        self.connect(self.listbox, SIGNAL("itemDoubleClicked(QListWidgetItem *)"), self.editTag)
        self.connect(self.okcancel, SIGNAL("ok"),self.OK)

        clicked = SIGNAL('clicked()')
        self.connect(edittag, clicked, self.editTag)
        self.connect(addtag, clicked, self.addTag)
        self.connect(removetag, clicked, self.removeTag)
        self.connect(prevaudio, clicked, self.prevAudio)
        self.connect(nextaudio, clicked, self.nextAudio)

        self.setMinimumSize(450,350)

        self.canceled = False

    def nextAudio(self):
        if self.currentrow < len(self.model.taginfo) - 1:
            self.save()
            self.loadFile(self.currentrow + 1)

    def prevAudio(self):
        if self.currentrow > 0 and len(self.model.taginfo) > 1:
            self.save()
            self.loadFile(self.currentrow - 1)

    def removeTag(self):
        row = self.listbox.currentRow()
        if row != -1:
            self.listbox.takeItem(row)

    def closeMe(self):
        self.model.undolevel += 1
        self.model.undo()
        self.canceled = True
        self.close()

    def closeEvent(self,event):
        if not self.canceled:
            self.model.undolevel += 1
        self.piclabel.close()
        QDialog.closeEvent(self,event)

    def save(self):
        tags = {}
        listitems = [unicode(self.listbox.item(row).text()).split(" = ") for row in xrange(self.listbox.count())]
        for tag, val in listitems:
            if tag in tags:
                tags[tag].append(val)
            else:
                tags[tag] = [val]
        toremove = [z for z in audioinfo.usertags(self.model.taginfo[self.currentrow]) if z not in tags]
        for tag in toremove:
            tags[tag] = ""
        tags["__image"] =  deepcopy(self.piclabel.images)
        self.model.setRowData(self.currentrow, tags)
        self.emit(SIGNAL('tagAvailable'))

    def OK(self):
        self.save()
        self.close()

    def addTag(self):
        win = EditTag(parent = self)
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.editTagBuddy)

    def editTag(self):
        """Opens a windows that allows the user
        to edit the tag in item(a QListWidgetItem that's supposed to
        be from self.listbox).

        If item is None then the currently selected item
        in self.listbox is used.

        After the value is edited, self.listbox is updated."""
        row = self.listbox.currentRow()
        if row != -1:
            prevtag = unicode(self.listbox.currentItem().text()).split(" = ")
            win = EditTag(prevtag, self)
            win.setModal(True)
            win.show()
            self.connect(win, SIGNAL("donewithmyshit"), self.editTagBuddy)

    def editTagBuddy(self, tag, value, prevtag = None):
        if prevtag is not None:
            self.listbox.currentItem().setText(tag + " = " + value)
        else:
            self.listbox.addItem(tag + " = " + value)
        self.listbox.sortItems()


    def loadFile(self, row):
        self.listbox.clear()
        items = []
        tags = self.model.taginfo[row]
        for item, val in  audioinfo.usertags(tags).items():
            if val and (type(val) is unicode):
                items.append(item + " = " + val)
            else:
                [items.append(item + " = " + z) for z in val]
        self.listbox.addItems(items)
        self.currentrow = row
        if tags.filetype != audioinfo.MP3:
            self.piclabel.setEnabled(False)
        if tags.images:
            self.piclabel.setImages(tags.images)
        else:
            self.piclabel.setImages(None)
        self.setWindowTitle(tags["__filename"])
        self.undolevel = self.model.undolevel


if __name__ == "__main__":
    app = QApplication(sys.argv)
    wid = ImportWindow()
    wid.resize(200,400)
    wid.show()
    app.exec_()

#app=QApplication(sys.argv)
#qb=TrackWindow(None,12,23)
#qb.show()
#app.exec_()