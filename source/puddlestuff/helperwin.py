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

class TrackWindow(QDialog):
    """Dialog that allows automatic numbering of tracks.
    Number the tracks in range(start, end)"""
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
        self.checkbox = QCheckBox("Add seperator ['/']")
        self.numtracks = QLineEdit()
        self.numtracks.setEnabled(False)
        self.numtracks.setMaximumWidth(50)
        self.hboxlayout2.addWidget(self.checkbox)
        self.hboxlayout2.addWidget(self.numtracks)
        
        self.hboxlayout3 = QHBoxLayout()
        self.ok = QPushButton("OK")
        self.cancel=QPushButton("Cancel")
        self.hboxlayout3.addWidget(self.ok)
        self.hboxlayout3.addWidget(self.cancel)
        
        self.vbox = QVBoxLayout(self)
        self.vbox.addLayout(self.hboxlayout)
        self.vbox.addLayout(self.hboxlayout2)
        self.vbox.addLayout(self.hboxlayout3)
        
        self.setLayout(self.vbox)
        self.connect(self.ok,SIGNAL('clicked()'),self.doStuff)
        self.connect(self.cancel,SIGNAL('clicked()'),self.close)
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
        if self.checkbox.checkState() == 2:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), unicode(self.numtracks.text())])
        else:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), ""])
        self.close()
        
class ImportWindow(QDialog):
    """Dialog that allows you to import a file to tags."""
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
        if filename == "" or filename is None:
            filedlg = QFileDialog()
            filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder',QDir.homePath()))
        if filename != "":
            try:
                f = open(filename)
            except IOError:
                ret = QMessageBox.question(self, "Error", "I could not access the file: " + filename + ". Do you want to choose another file?",
                        "&Yes, choose another", "&No, close this window.")
                if ret == 0:
                    self.openFile()
                else:
                    self.close()
                return
            i = 0
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
        self.emit(SIGNAL("Newtags"), self.dicttags)
        self.close()

class ListModel(QAbstractTableModel):
    """Called ListModel instead of tabelsomething, because
    it facilitates putting shit in a list."""
    def __init__(self, model = None, row = 0):
        """model is of type puddleobjects.TagModel.
        All the taginfo and stuff like that is imported from there.
        
        row is the row that you want to be shown. i.e the file
        that is to edited."""
        QAbstractTableModel.__init__(self)
        if model is None:
            self.taginfo = []
        else:
            self.taginfo = model.taginfo
            self.setRowData = model.setRowData
            self.tagValue(row)
            self.model = model
        self.undolevel = 0
        self.reset()
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
            return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            try:
                if section == 0:
                    return QVariant("Tag Value")
            except IndexError:
                return QVariant()
        return QVariant(self.currentTag[section][0])
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.currentTag)):
            return QVariant()
        if (role == Qt.DisplayRole) or (role == Qt.ToolTipRole) or (role == Qt.EditRole):
            try:
                if not self.currentTag[index.row()][0].startswith("__"):
                    return QVariant(self.currentTag[index.row()][1])
            except TypeError:
                pdb.set_trace()
        return QVariant()
    
    def rowCount(self, index = QModelIndex()):
        return len(self.currentTag)
    
    def columnCount(self, index=QModelIndex()):
        return 1
    
    def tagValue(self, row):
        self.currentRow = row
        self.currentTag = sorted([list(z) for z in self.taginfo[row].items() 
                                if (not type(z[0]) is int) and (not z[0].startswith("__"))])
        self.reset()
    
    def setData(self, index, value, role = Qt.EditRole):
        if index.isValid() and 0 <= index.row() < len(self.currentTag):
            self.currentTag[index.row()][1] = unicode(value.toString())
            self.setRowData(self.currentRow, dict([self.currentTag[index.row()]]), True)
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        index, index)
            return True
        return False
        
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index)|
                            Qt.ItemIsEditable| Qt.ItemIsDropEnabled)

    def insertRow(self, row, count = None, parent = QModelIndex(), tag = None):
        if row == -1:
            row = self.rowCount()        
        self.beginInsertRows(parent, row, row)
        self.currentTag.insert(row, tag)
        self.endInsertRows()
        self.reset()
        return True

class Label(QLabel):
    """Just a QLabel that sends a clicked() signal
    when left-clicked."""
    def __init__ (self, text = "", parent = None, f = 0):
        QLabel.__init__ (self, text, parent)
    
    def mouseReleaseEvent(self, event):
      
      if event.button() == Qt.LeftButton:
        self.emit(SIGNAL("clicked()"))
      QLabel.mousePressEvent(self, event)

class PicWin(QDialog):
    """A windows that shows an image."""
    def __init__(self, pixmap = None, parent = None):
        """Loads the image specified in QPixmap pixmap.
        If picture is clicked, the window closes.
        
        If you don't want to load an image when the class
        is created, let pixmap = None and call setImage later."""
        QDialog.__init__(self, parent)
        self.setWindowFlags(Qt.Tool)
        vbox = QVBoxLayout()
        self.label = Label()
        
        if pixmap is not None:
            self.label.setPixmap(pixmap)
            self.setMaximumSize(pixmap.size())
            self.setMinimumSize(pixmap.size())
        
        vbox.addWidget(self.label)
        self.setLayout(vbox)
        
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
    (Because the user mightc choose to edit a different tag,
    then the one that was chosen)"""
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
                self.tagcombo.setCurrentIndex(0)
            

            self.value.setPlainText(tag[1])
        
        [self.vbox.addWidget(z) for z in [label, self.tagcombo, label1, self.value]]
        okcancel = OKCancel()
        okcancel.ok.setText("&Save")
        self.vbox.addLayout(okcancel)
        self.setLayout(self.vbox)
        
        self.connect(okcancel, SIGNAL("ok"), self.ok)
        self.connect(okcancel, SIGNAL("cancel"), self.close)
        
    def ok(self):
        self.emit(SIGNAL("donewithmyshit"), unicode(self.tagcombo.currentText()), unicode(self.value.toPlainText()), self.prevtag)
        self.close()

class ExTags(QDialog):
    """A dialog that shows you the tags in a file 
    
    In addition, the file's image tag is shown."""
    def __init__(self, model = None, row = 0, parent = None):
        """If filename is not None, then I'll just load that file.
        Otherwise the window is loaded.
        
        If the filename is specfied, but does not exist(or isn't valid)
        then the user is asked to choose another file."""
        QDialog.__init__(self, parent)        
        self.listbox = QListWidget()        
        
        self.pixmap = QPixmap()
        
        self.piclabel = Label()
        self.piclabel.setFrameStyle(QFrame.Box)
        self.piclabel.setMinimumSize(150, 150)
        self.piclabel.setMaximumSize(150, 150)
        self.piclabel.setAlignment(Qt.AlignCenter)
        
        if type(model) is not str:
            self.model = model
            image = self.model.taginfo[row]["__image"]
            if image is not None and image != "":
                image = QImage().fromData(image[0])
                if not image.isNull():
                    self.pixmap = QPixmap.fromImage(image)
                    self.piclabel.setPixmap(self.pixmap.scaled(self.piclabel.size(), Qt.KeepAspectRatio))
            self.setWindowTitle(self.model.taginfo[row]["__filename"])
            self.loadFile(row)
 
        addtag = QPushButton('&Add Tag')
        edittag = QPushButton('&Edit Tag')
        removetag = QPushButton('&Remove Tag')
        
        self.okcancel = OKCancel()
        
        vbox = QVBoxLayout()
        vbox.addWidget(self.piclabel,1)
        vbox.addWidget(addtag,0)
        vbox.addWidget(edittag,0)
        vbox.addWidget(removetag,0)        
        vbox.addStretch()
        
        self.hbox = QHBoxLayout()        
        self.hbox.addWidget(self.listbox)        
        self.hbox.addLayout(vbox)
        
        self.vbox = QVBoxLayout()
        self.vbox.addLayout(self.hbox)
        self.vbox.addLayout(self.okcancel)
        self.setLayout(self.vbox)  
        

        self.connect(self.okcancel, SIGNAL("cancel"), self.closeMe)
        self.connect(self.listbox, SIGNAL("itemDoubleClicked(QListWidgetItem *)"), self.editTag)
        self.connect(self.piclabel,SIGNAL("clicked()"), self.fullPic)
        self.connect(self.okcancel, SIGNAL("ok"),self.OK)
        
        self.connect(edittag, SIGNAL('clicked()'), self.editTag)
        self.connect(addtag, SIGNAL('clicked()'), self.addTag)
        self.connect(removetag, SIGNAL('clicked()'), self.removeTag)
        

        self.setMinimumSize(450,350)
        
        self.piclabel.setContextMenuPolicy(Qt.ActionsContextMenu)
        
        self.savepic = QAction("&Save picture", self)
        self.piclabel.addAction(self.savepic)
        self.connect(self.savepic, SIGNAL("triggered()"), self.savePic)

        #Creating it here so that I can know when it is visible or not.
        self.win = PicWin()
        self.canceled = False
            
    def removeTag(self):
        row = self.listbox.currentRow()
        if row != -1:
            self.listbox.takeItem(row)
            del(self.currentfile[row])
            
    def closeMe(self):
        self.model.undolevel += 1
        self.model.undo()
        self.canceled = True
        self.close()
        
    def closeEvent(self,event):
        self.win.close()
        if not self.canceled:
            self.model.undolevel += 1
        QWidget.closeEvent(self,event)
    
    def fullPic(self):
        """Opens a dialog with the Fullsized image of the current file."""
        self.win.setImage(self.pixmap)
        if self.win.isVisible():
            #If the image is clicked, but the fullsize image is visible
            self.win.setVisible(False)
        else:
            self.win.show()
	
    def OK(self):
        tags = [z[0] for z in self.currentfile]
        toremove = [z for z in self.model.taginfo[self.currentrow] if not z.startswith("__") and z not in tags]        
        self.currentfile.extend([[z,""] for z in toremove])
        self.model.setRowData(self.currentrow, dict(self.currentfile))
        self.emit(SIGNAL('tagAvailable'))
        self.close()
                    
    def savePic(self):
        """Opens a dialog that allows the user to save,
        the image in the current file to disk."""
        if self.pixmap:
            filedlg = QFileDialog()
            #filedlg.setFilters(["JPEG (*.jpg)", "PNG (*.png)","Windows Bitmap (*.bmp)","X11 Bitmap (*.xbm)","X11 Bitmap (*.xpm)"])
            #FIXME: For some fucking reason, even though the filter is set up correctly,
            #filedlg.currentFilter() is the first in the list no matter what is chosen.
            filedlg.setFilters(["PNG (*.png)","All Files (*)"])
            filename = unicode(filedlg.getSaveFileName(self,
                    'Save as...',"~", "PNG Images(*.png);;All Files (*)"))
            
            if os.path.exists(os.path.dirname(filename)):
                self.pixmap.save(filename, "PNG")
    
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
            win = EditTag(self.currentfile[row], self)            
            win.setModal(True)
            win.show()
            self.connect(win, SIGNAL("donewithmyshit"), self.editTagBuddy)
    
    def editTagBuddy(self, tag, value, prevtag = None):
        if prevtag is not None:
            try:
                x = self.currentfile.index(prevtag)
            except ValueError:
                x = -1
            if x >= 0 :
                if prevtag[0] == tag:
                    self.currentfile[x][1] = value
                else:
                    self.currentfile[x] = [tag, value]
            self.listbox.item(x).setText(tag + " = " + value)
        else:
            try:
                x = [z[0] for z in self.currentfile].index(tag)
                self.currentfile[x] = [tag, value]
            except ValueError:
                self.currentfile.append([tag, value])
                self.listbox.addItem(tag + " = " + value)
        
    
    def loadFile(self, row):
        self.listbox.clear()
        self.currentfile = sorted([[tag, val] for tag, val in  self.model.taginfo[row].items() if not tag.startswith('__') and val != ""])
        self.listbox.addItems([item[0] + " = " + item[1] for item in self.currentfile])
        self.currentrow = row
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