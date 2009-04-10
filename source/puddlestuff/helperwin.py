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
from puddleobjects import OKCancel, partial, MoveButtons, HORIZONTAL, VERTICAL, ListButtons
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
    """A widget that shows a file's pictures.

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
    def __init__ (self, images = None, parent = None, readonly = None, buttons = False):
        QWidget.__init__(self, parent)
        self.label = Label()
        self.label.setFrameStyle(QFrame.Box)
        self.label.setMargin(0)
        self.label.setMinimumSize(180, 150)
        self.label.setMaximumSize(180, 150)
        self.label.setAlignment(Qt.AlignCenter)

        self._image_desc = QLineEdit(self)
        self.connect(self._image_desc, SIGNAL('textEdited (const QString&)'),
                    self.setDescription)
        self._image_type = QComboBox(self)
        self._image_type.addItems(audioinfo.IMAGETYPES)
        self.connect(self._image_type, SIGNAL('currentIndexChanged (int)'),
                        self.setType)
        controls = QHBoxLayout()

        dbox = QVBoxLayout()
        label = QLabel('&Description')
        label.setBuddy(self._image_desc)
        dbox.addWidget(label)
        dbox.addWidget(self._image_desc)
        controls.addLayout(dbox)

        dbox = QVBoxLayout()
        label = QLabel('&Type')
        label.setBuddy(self._image_type)
        dbox.addWidget(label)
        dbox.addWidget(self._image_type)
        controls.addLayout(dbox)

        self.showbuttons = True

        if not readonly:
            self.readonly = []
        self.blanks = 0

        self.next = QPushButton('&>>')
        self.prev = QPushButton('&<<')
        self.connect(self.next, SIGNAL('clicked()'), self.nextImage)
        self.connect(self.prev, SIGNAL('clicked()'), self.prevImage)

        if not images:
            images = []
        self.setImages(images)

        movebuttons = QHBoxLayout()
        movebuttons.addStretch()
        movebuttons.addWidget(self.prev)
        movebuttons.addWidget(self.next)
        movebuttons.addStretch()

        vbox = QVBoxLayout()
        h = QHBoxLayout(); h.addStretch(); h.addWidget(self.label); h.addStretch()
        vbox.addLayout(h)
        vbox.setMargin(0)
        vbox.addLayout(controls)
        vbox.addLayout(movebuttons)
        vbox.setAlignment(Qt.AlignCenter)

        self.connect(self.label, SIGNAL('clicked()'), self.maxImage)

        hbox = QHBoxLayout()
        hbox.addLayout(vbox)
        self.setLayout(hbox)

        if buttons:
            listbuttons = ListButtons()
            self.addpic = listbuttons.add
            self.removepic = listbuttons.remove
            self.editpic = listbuttons.edit
            self.savepic = QToolButton()
            self.savepic.setIcon(QIcon(':/save.png'))
            self.savepic.setIconSize(QSize(16,16))
            listbuttons.insertWidget(3,self.savepic)
            listbuttons.moveup.hide()
            listbuttons.movedown.hide()
            signal = SIGNAL('clicked()')
            hbox.addLayout(listbuttons)

        else:
            self.label.setContextMenuPolicy(Qt.ActionsContextMenu)
            self.savepic = QAction("&Save picture", self)
            self.label.addAction(self.savepic)

            self.addpic = QAction("&Add picture", self)
            self.label.addAction(self.addpic)

            self.removepic = QAction("&Remove picture", self)
            self.label.addAction(self.removepic)

            self.editpic = QAction("&Change picture", self)
            self.label.addAction(self.editpic)
            signal = SIGNAL('triggered()')

        self.connect(self.addpic, signal, self.addImage)
        self.connect(self.removepic, signal, self.removeImage)
        self.edit = partial(self.addImage, True)
        self.connect(self.editpic, signal, self.edit)
        self.connect(self.savepic, signal, self.saveToFile)

        self.win = PicWin(parent = self)
        self._currentImage = -1

    def setDescription(self, text):
        self.images[self.currentImage]['description'] = unicode(text)

    def setType(self, index):
        self.images[self.currentImage]['imagetype'] = index

    def addImage(self, edit = False, filename = None):
        if not filename:
            filedlg = QFileDialog()
            filename = unicode(filedlg.getOpenFileName(self,
                    'Select Image...',"~", "JPEG Images (*.jpg);;PNG Images (*.png);;All Files(*.*)"))
        data = open(filename, 'rb').read()
        image = QImage()
        if image.loadFromData(data):
            pic = {'data': data, 'height': image.height(),
                    'width': image.width(), 'size': len(data),
                    'mime': 'image/jpeg', 'description': 'Enter description',
                    'imagetype': 3}
            if edit and self.images:
                desc = self.images[self.currentImage]['description']
                self.images[self.currentImage].update(pic)
                self.currentImage = self.currentImage
            else:
                if not self.images:
                    self.setImages([pic])
                else:
                    self.images.append(pic)
                    self.currentImage = len(self.images) - 1

    def close(self):
        self.win.close()
        QWidget.close(self)

    def enableButtons(self):
        if not self.images:
            self.next.setEnabled(False)
            self.prev.setEnabled(False)
        else:
            if self.currentImage >= len(self.images) - 1:
                self.next.setEnabled(False)
            else:
                self.next.setEnabled(True)
            if self.currentImage <= 0:
                self.prev.setEnabled(False)
            else:
                self.prev.setEnabled(True)

        if not self.showbuttons and not self.next.isEnabled() and not self.prev.isEnabled():
            self.next.hide()
            self.prev.hide()
        else:
            self.next.show()
            self.prev.show()

    def _getImage(self):
        return self._currentImage

    def _setCurrentImage(self, num):
        try:
            while True:
                image = QImage().fromData(self.images[num]['data'])
                if image.isNull(): #Badly written data, which isn't useful in any way.
                    del(self.images[num])
                else:
                    break
            [action.setEnabled(True) for action in
                    (self.editpic, self.savepic, self.removepic)]
        except IndexError:
            [action.setEnabled(False) for action in
                    (self.editpic, self.savepic, self.removepic)]
            self.label.setPixmap(QPixmap())
            return

        if num in self.readonly:
            self.editpic.setEnabled(False)
            self.removepic.setEnabled(False)
        self.pixmap = QPixmap.fromImage(image)
        self.win.setImage(self.pixmap)
        self.label.setPixmap(self.pixmap.scaled(self.label.size(), Qt.KeepAspectRatio))
        try:
            self._image_desc.setText(self.images[num]['description'])
            self._image_desc.setEnabled(True)
        except KeyError:
            self._image_desc.setEnabled(False)
        try:
            self._image_type.setCurrentIndex(self.images[num]['imagetype'])
            self._image_type.setEnabled(True)
        except KeyError:
            self._image_type.setEnabled(False)
        self._currentImage = num
        self.label.setFrameStyle(QFrame.NoFrame)
        self.enableButtons()

    currentImage = property(_getImage, _setCurrentImage,"""Get or set the index of
    the current image. If the index isn't valid
    then a blank image is loaded.""")

    def maxImage(self):
        if self.pixmap:
            if self.win.isVisible():
                self.win.hide()
            else:
                self.win = PicWin(self.pixmap, self)
                self.win.show()

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

    def setImages(self, images):
        if images:
            self.images = images
            self.currentImage = 0
        else:
            self.label.setFrameStyle(QFrame.Box)
            self.label.setPixmap(QPixmap())
            self.pixmap = None
            self.images = []
        self.enableButtons()


    def removeImage(self):
        if len(self.images) >= 1:
            del(self.images[self.currentImage])
            if self.currentImage >= len(self.images) - 1 and self.currentImage > 0:
                self.currentImage = len(self.images) - 1
            else:
                self.currentImage =  self.currentImage

    def addBlanks(self, *filenames):
        images = []
        for i, filename in enumerate(filenames):
            image = QImage()
            if image.load(filename):
                try:
                    data = open(filename, 'rb').read()
                except IOError, e:
                    if filename.startswith(u':/'):
                        ba = QByteArray()
                        data = QBuffer(ba)
                        data.open(QIODevice.WriteOnly)
                        image.save(data, "JPG")
                        data = data.data()
                    else:
                        raise e
                pic = {'data': data}
                images.append(pic)
        self.blanks = len(filenames)
        self.setImages(images)


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
        vbox.setMargin(0)
        vbox.addWidget(self.label)
        self.setLayout(vbox)

        if pixmap is not None:
            self.setImage(pixmap)

        self.connect(self.label, SIGNAL('clicked()'), self.close)

    def setImage(self, pixmap):
        self.label.setPixmap(pixmap)
        self.setMaximumSize(pixmap.size())
        self.setMinimumSize(pixmap.size())
        self.resize(pixmap.size())


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
    def __init__(self, model, row = 0, parent = None):
        """model -> is a puddlestuff.TableModel object
        row -> the row that contains the file to be displayed
        """
        QDialog.__init__(self, parent)
        self.listbox = QListWidget()
        self.piclabel = PicWidget(buttons = True)

        buttons = MoveButtons(model.taginfo, row)

        self.okcancel = OKCancel()

        listbuttons = ListButtons()
        listbuttons.moveup.hide()
        listbuttons.movedown.hide()

        listframe = QFrame()
        listframe.setFrameStyle(QFrame.Box)
        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox,1)
        hbox.addLayout(listbuttons, 0)
        listframe.setLayout(hbox)

        imageframe = QFrame()
        imageframe.setFrameStyle(QFrame.Box)
        vbox = QVBoxLayout()
        vbox.setMargin(0)
        vbox.addWidget(self.piclabel)
        vbox.addStretch()
        imageframe.setLayout(vbox)

        hbox = QHBoxLayout()
        hbox.addWidget(listframe)
        hbox.addSpacing(4)
        hbox.addWidget(imageframe)

        layout = QVBoxLayout()
        layout.addLayout(hbox)
        layout.addLayout(self.okcancel)
        self.okcancel.insertWidget(0, buttons)
        self.setLayout(layout)

        self.connect(self.okcancel, SIGNAL("cancel"), self.closeMe)
        self.connect(self.listbox, SIGNAL("itemDoubleClicked(QListWidgetItem *)"), self.editTag)
        self.connect(self.okcancel, SIGNAL("ok"),self.OK)

        clicked = SIGNAL('clicked()')
        self.connect(listbuttons.edit, clicked, self.editTag)
        self.connect(listbuttons.add, clicked, self.addTag)
        self.connect(listbuttons.remove, clicked, self.removeTag)

        self.setMinimumSize(450,350)

        self.canceled = False

        if not isinstance(model, basestring):
            self.model = model
            self.loadFile(row)
            self.connect(buttons, SIGNAL('indexChanged'), self.loadFile)

    def removeTag(self):
        row = self.listbox.currentRow()
        if row != -1:
            self.listbox.takeItem(row)
        self.filechanged = True

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
        audio = self.model.taginfo[self.currentrow]
        if not self.piclabel.images:
            images = None
        else:
            images = self.piclabel.images
        if (images != audio['__image']) or self.filechanged:
            tags = {}
            listitems = [unicode(self.listbox.item(row).text()).split(" = ") for row in xrange(self.listbox.count())]
            for tag, val in listitems:
                if tag in tags:
                    tags[tag].append(val)
                else:
                    tags[tag] = [val]
            toremove = [z for z in self.model.taginfo[self.currentrow] if z not in tags and z not in audioinfo.INFOTAGS]
            for tag in toremove:
                tags[tag] = ""
            keys = ['data', 'mime', 'description', 'imagetype']
            pics = [dict([(key, z[key]) for key in keys if key in z]) for z in images]
            tags["__image"] =  [audio.image(**pic) for pic in pics]
            self.model.setRowData(self.currentrow, tags)
            self.emit(SIGNAL('tagChanged()'))

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
        self.filechanged = True


    def loadFile(self, row):
        self.filechanged = False
        self.listbox.clear()
        items = []
        tags = self.model.taginfo[row]
        for item, val in audioinfo.usertags(tags).items():
            [items.append(item + " = " + z) for z in val]
        self.listbox.addItems(items)
        self.currentrow = row
        self.piclabel.setEnabled(False)
        if '__library' not in tags:
            if hasattr(tags, 'image'):
                self.piclabel.setEnabled(True)
                if tags.images:
                    self.piclabel.setImages(deepcopy(tags.images))
                else:
                    self.piclabel.setImages(None)
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
