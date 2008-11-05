#!/usr/bin/env python

"""
A class that contains objects used throughout puddletag"""

"""puddleobjects.py

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
import sys,os, audioinfo, pdb
from operator import itemgetter
from copy import copy
from subprocess import Popen
from os import path
from audioinfo import PATH, FILENAME

from itertools import groupby # for unique function.
from bisect import bisect_left, insort_left # for unique function.


def unique(seq, stable=False):
    """unique(seq, stable=False): return a list of the elements in seq in arbitrary
    order, but without duplicates.
    If stable=True it keeps the original element order (using slower algorithms)."""
    # Developed from Tim Peters version:
    #   http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52560

    #if uniqueDebug and len(str(seq))<50: print "Input:", seq # For debugging.

    # Special case of an empty s:
    if not seq: return []

    # if it's a set:
    if isinstance(seq, set): return list(seq)

    if stable:
        # Try with a set:
        seqSet= set()
        result = []
        try:
            for e in seq:
                if e not in seqSet:
                    result.append(e)
                    seqSet.add(e)
        except TypeError:
            pass # move on to the next method
        else:
            #if uniqueDebug: print "Stable, set."
            return result

        # Since you can't hash all elements, use a bisection on sorted elements
        result = []
        sortedElem = []
        try:
            for elem in seq:
                pos = bisect_left(sortedElem, elem)
                if pos >= len(sortedElem) or sortedElem[pos] != elem:
                    insort_left(sortedElem, elem)
                    result.append(elem)
        except TypeError:
            pass  # Move on to the next method
        else:
            #if uniqueDebug: print "Stable, bisect."
            return result
    else: # Not stable
        # Try using a set first, because it's the fastest and it usually works
        try:
            u = set(seq)
        except TypeError:
            pass # move on to the next method
        else:
            #if uniqueDebug: print "Unstable, set."
            return list(u)

        # Elements can't be hashed, so bring equal items together with a sort and
        # remove them out in a single pass.
        try:
            t = sorted(seq)
        except TypeError:
            pass  # Move on to the next method
        else:
            #if uniqueDebug: print "Unstable, sorted."
            return [elem for elem,group in groupby(t)]

    # Brute force:
    result = []
    for elem in seq:
        if elem not in result:
            result.append(elem)
    #if uniqueDebug: print "Brute force (" + ("Unstable","Stable")[stable] + ")."
    return result

def partial(func, arg):
    def callme():
        return func(arg)
    return callme

def safe_name(name, to = None):
    """Make a filename safe for use (remove some special chars)
    
    If any special chars are found they are replaced by to."""
    if not to:
        to = ""
    else:
        to = unicode(to)
    escaped = ""
    for ch in name:
        if ch not in r'/\*?;"|:': escaped = escaped + ch
        else: escaped = escaped + to
    if not escaped: return '""'
    return escaped
        
class HeaderSetting(QDialog):
    """A dialog that allows you to edit the header of a TableShit widget."""
    def __init__(self, tags = None, parent = None, showok = True):
        QDialog.__init__(self, parent)
        self.listbox = ListBox()
        self.tags = [list(z) for z in tags]
        self.listbox.addItems([z[0] for z in self.tags])
        self.listbox.setSelectionMode(self.listbox.ExtendedSelection)
        
        self.vbox = QVBoxLayout()
        self.vboxgrid = QGridLayout()
        self.textname = QLineEdit()
        self.tag = QLineEdit()
        self.buttonlist = ButtonLayout()
        self.buttonlist.edit.setVisible(False)
        self.vboxgrid.addWidget(QLabel("Name"),0,0)
        self.vboxgrid.addWidget(self.textname,0,1)
        self.vboxgrid.addWidget(QLabel("Tag"), 1,0)
        self.vboxgrid.addWidget(self.tag,1,1)
        self.vboxgrid.addLayout(self.buttonlist,2,0)
        self.vboxgrid.setColumnStretch(0,0)
        
        self.vbox.addLayout(self.vboxgrid)
        self.vbox.addStretch()

        self.grid = QGridLayout()
        self.grid.addWidget(self.listbox,0,0)
        self.grid.addLayout(self.vbox,0,1)
        self.grid.setColumnStretch(1,2)
        
        self.setLayout(self.grid)
        self.connect(self.listbox, SIGNAL("currentItemChanged (QListWidgetItem *,QListWidgetItem *)"), self.fillEdits)
        self.connect(self.listbox, SIGNAL("itemSelectionChanged()"),self.enableEdits)
        
        
        self.okbuttons = OKCancel()
        if showok is True:        
            self.grid.addLayout(self.okbuttons, 1,0,1,2)
        
        self.connect(self.okbuttons, SIGNAL("ok"), self.okClicked)
        self.connect(self.okbuttons, SIGNAL("cancel"), self.close)
        self.connect(self.textname, SIGNAL("textChanged (const QString&)"), self.updateList)
        self.connect(self.buttonlist, SIGNAL("add"), self.add)
        self.connect(self.buttonlist, SIGNAL("moveup"), self.moveup)
        self.connect(self.buttonlist, SIGNAL("movedown"), self.movedown)
        self.connect(self.buttonlist, SIGNAL("remove"), self.remove)
        
        self.listbox.setCurrentRow(0)
    
    def enableEdits(self):
        if len(self.listbox.selectedItems()) > 1:
            self.textname.setEnabled(False)
            self.tag.setEnabled(False)
            return
        self.textname.setEnabled(True)
        self.tag.setEnabled(True)
    
    def remove(self):
        if len(self.tags) == 1: return
        self.disconnect(self.textname, SIGNAL("textChanged (const QString&)"), self.updateList)
        self.disconnect(self.listbox, SIGNAL("currentItemChanged (QListWidgetItem *,QListWidgetItem *)"), self.fillEdits)
        self.listbox.removeSelected(self.tags)
        row = self.listbox.currentRow()
        #self.listbox.clear()
        #self.listbox.addItems([z[0] for z in self.tags])
        
        if row == 0:
            self.listbox.setCurrentRow(0)
        elif row + 1 < self.listbox.count():
            self.listbox.setCurrentRow(row+1)
        else:
            self.listbox.setCurrentRow(self.listbox.count() -1)
        self.fillEdits(self.listbox.currentItem(), None)
        self.connect(self.textname, SIGNAL("textChanged (const QString&)"), self.updateList)
        self.connect(self.listbox, SIGNAL("currentItemChanged (QListWidgetItem *,QListWidgetItem *)"), self.fillEdits)
    
    def moveup(self):
        self.listbox.moveUp(self.tags)
    
    def movedown(self):
        self.listbox.moveDown(self.tags)
        
    def updateList(self, text):
        self.listbox.currentItem().setText(text)
            
    def fillEdits(self, current, prev):
        row = self.listbox.row(prev)
        try: #An error is raised if the last item has just been removed
            if row > -1:
                self.tags[row][0] = unicode(self.textname.text())
                self.tags[row][1] = unicode(self.tag.text())
        except IndexError:
            pass
                
        row = self.listbox.row(current)
        if row > -1:
            self.textname.setText(self.tags[row][0])
            self.tag.setText(self.tags[row][1])
    
    def okClicked(self):
        row = self.listbox.currentRow()
        if row > -1:
            self.tags[row][0] = unicode(self.textname.text())
            self.tags[row][1] = unicode(self.tag.text())
        self.emit(SIGNAL("headerChanged"),[z for z in self.tags])
        self.close()
    
    def add(self):
        row = self.listbox.count()
        self.tags.append(["",""])
        self.listbox.addItem("")
        [self.listbox.setItemSelected(item, False) for item in self.listbox.selectedItems()]
        self.listbox.setCurrentRow(row)
        self.textname.setFocus()

class ProgressWin(QProgressDialog):
    def __init__(self, parent=None, maximum = 100, table = None):
        QProgressDialog.__init__(self, "", "Cancel", 0, maximum, parent)
        self.setModal(True)
        self.setWindowTitle("Please Wait...")
        if table is not None:
            self.connect(table.model(),SIGNAL("fileError"), self.modelError)
    
    def modelError(self, tags = None):
        self.hide()
    
    def updateVal(self):
        self.show()
        self.setValue(self.value() + 1)

class compare:
    "Natural sorting class."
    def try_int(self, s):
        "Convert to integer if possible."
        try: return int(s)
        except: return s

    def natsort_key(self, s):
        "Used internally to get a tuple by which s is sorted."
        import re
        return map(self.try_int, re.findall(r'(\d+|\D+)', s))
    
    def natcmp(self, a, b):
        "Natural string comparison, case sensitive."
        return cmp(self.natsort_key(a), self.natsort_key(b))
    
    def natcasecmp(self, a, b):
        "Natural string comparison, ignores case."
        return self.natcmp(a.lower(), b.lower())
    
class OKCancel(QHBoxLayout):
    """Yes, I know about QButtonLayout, but I'm not using PyQt4.2 here."""
    def __init__(self, parent = None):
        QHBoxLayout.__init__(self, parent)
        
        self.addStretch()
        
        self.ok = QPushButton("&OK")
        self.cancel = QPushButton("&Cancel")
        self.ok.setDefault(True)
        
        self.addWidget(self.ok)
        self.addWidget(self.cancel)
            
        self.connect(self.ok, SIGNAL("clicked()"), self.yes)
        self.connect(self.cancel, SIGNAL("clicked()"), self.no)
        
    def yes(self):
        self.emit(SIGNAL("ok"))
    
    def no(self):
        self.emit(SIGNAL("cancel"))
        
class ButtonLayout(QVBoxLayout):
    """A Layout that contains, five buttons usually
    associated with listboxes. They are
    add, edit, movedown, moveup and remove.
    
    Each button, when clicked sends signal with the
    buttons name. e.g. add sends SIGNAL("add")."""
    
    def __init__(self, parent = None):
        QVBoxLayout.__init__(self, parent)
        self.add = QPushButton("&Add")
        self.remove = QPushButton("&Remove")
        self.moveup = QPushButton("&Move Up")
        self.movedown = QPushButton("&Move Down")
        self.edit = QPushButton("&Edit")
        
        self.widgets = [self.add, self.edit, self.remove, self.moveup, self.movedown]
        [self.addWidget(widget) for widget in self.widgets]
        self.addStretch()
        
        clicked = SIGNAL("clicked()")
        self.connect(self.add, clicked, self.addClicked)
        self.connect(self.remove, clicked, self.removeClicked)
        self.connect(self.moveup, clicked, self.moveupClicked)
        self.connect(self.movedown, clicked, self.movedownClicked)
        self.connect(self.edit, clicked, self.editClicked)
        
    def addClicked(self):
        self.emit(SIGNAL("add"))
    
    def removeClicked(self):
        self.emit(SIGNAL("remove"))
    
    def moveupClicked(self):
        self.emit(SIGNAL("moveup"))
    
    def movedownClicked(self):
        self.emit(SIGNAL("movedown"))

    def editClicked(self):
        self.emit(SIGNAL("edit"))

class ListBox(QListWidget):
    """Puddletag's replacement of QListWidget.
    
    Three methods are defined.    
    removeSelected, moveUp and moveDown.
    See docstrings for more info"""
    def __init__(self, parent = None):
        QListWidget.__init__(self, parent)
    
    def removeSelected(self, yourlist = None, rows = None):
        """Removes the currently selected items.
        If yourlist is not None, then the selected
        items are removed for yourlist also. Note, that
        the indexes of the items in yourlist and the listbox
        has to correspond.
        
        If you want to remove anything other than the selected, 
        just set rows to a list of integers."""
        if rows is None:
            rows = [self.row(item) for item in self.selectedItems()]
        conter = 0
        for row in rows:
            row = row - conter
            if yourlist is not None:
                for i, item in enumerate(yourlist):
                    if i > row:
                        yourlist[i -1] = yourlist[i]
                del(yourlist[len(yourlist) - 1])        
            self.takeItem(row)
            conter += 1        
    
    def moveUp(self, yourlist = None, rows = None):
        """Moves the currently selected items up one place.
        If yourlist is not None, then the indexes of yourlist
        are updated in tandem. Note, that
        the indexes of the items in yourlist and the listbox
        has to correspond.
        
        rows can be any list of integers"""
        if rows is None:        
            rows = [self.row(item) for item in self.selectedItems()]
        def inline(rows):
            if (rows == []) or (0 in rows): return
            row = rows[0]
            item = self.takeItem(row - 1)
            self.insertItem(row, item)
        
            if yourlist is not None:
                what = yourlist[row - 1]
                yourlist[row - 1] = yourlist[row]
                yourlist[row] = what
            del(rows[0])
            inline(rows)
        inline(rows)
        
    def moveDown(self, yourlist = None, rows = None):
        """See moveup. It's exactly the opposite."""
        if rows is None:        
            rows = [self.row(item) for item in self.selectedItems()]
        
        if (rows == []) or ((self.count() - 1) in rows): return
        
        #moveDown doesn't work with contiguous selections that well.
        if (rows == range(rows[0], rows[-1] + 1)) and (len(rows) > 1):
            row = rows[0]
            item = self.takeItem(row + len(rows))
            self.insertItem(row, item)
            
            if yourlist is not None:
                what = yourlist[row + len(rows)]
                for i,z in enumerate(reversed(yourlist)):
                    yourlist[i + 1] = yourlist[row]
                yourlist[row[0]] = what
                
                
        def inline(rows):
            if (rows == []) or ((self.count() - 1) in rows): return
            row = rows[0]
            item = self.takeItem(row + 1)
            self.insertItem(row, item)
        
            if yourlist is not None:
                what = yourlist[row + 1]
                yourlist[row + 1] = yourlist[row]
                yourlist[row] = what
            del(rows[0])
            inline(rows)
        inline(rows)

        
class TagModel(QAbstractTableModel):
    """The model used in TableShit
    Methods you shoud take not of are(read docstrings for more):
    
    setData -> As per the usual model, can only write one tag at a time.
    setRowData -> Writes a bunch of tags at once.
    undo -> undo's changes.
        
    """
    def __init__(self, headerdata, taginfo = None):
        """Load tags. 
        
        headerdata must be a list of tuples
        where the first item is the displayrole and the second
        the tag to be used.
        
        taginfo should be a list of dictionaries
        where each dictionary represents a tag
        of a file. See audioinfo for more details.
        
        >>> headerdata = [("Artist", "artist"), ("Title", title")]
        >>> taginfo = [{"artist":"Gene Watson", "title": "Unknown"},
                        {"artist": "Keith Sweat", "title": "Nobody"}]
                        """
        QAbstractTableModel.__init__(self)
        self.headerdata = headerdata
        if taginfo is not None:
            self.taginfo = unique(taginfo)
        else:
            self.taginfo = []
        self.undolevel = 0
        self.reset()
    
    def undo(self):
        """Undos the last action.
        
        Basically, if a tag has a key which is = self.undolevel - 1,
        then the tag is updated with the dictionary in that key.
        
        setRowData does not modify the undoleve unless you explicitely tell
        it, but setData does modify the undolevel.
        
        It is recommended that you use consecutive indexes for self.undolevel."""
        
        if self.undolevel <= 0:
            self.undolevel = 0
            return
        level = self.undolevel - 1
        for row, file in enumerate(self.taginfo):
            if level in file:
                self.setRowData(row, file[level])
                del(file[level])            
        self.undolevel -= 1
        
    def supportedDropActions(self):
        return Qt.CopyAction
    
    def dropMimeData(self, data, action, row, column, parent = QModelIndex()):
        return True
        
    def load(self,taginfo,headerdata=None, append = False):
        """Loads tags as in __init__.
        If append is true, then the tags are just appended."""
        if headerdata is not None:
            self.headerdata = headerdata
        if append:
            self.taginfo.extend(taginfo)
        else:
            self.taginfo = taginfo
        self.taginfo = unique(self.taginfo)
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
                return QVariant(self.headerdata[section][0])
            except IndexError:
                return QVariant()
        return QVariant(int(section + 1))
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.taginfo)):
            return QVariant()
        column = index.column()
        if (role == Qt.DisplayRole) or (role == Qt.ToolTipRole) or (role == Qt.EditRole):
            try:
                return QVariant(self.taginfo[index.row()][self.headerdata[column][1]])
            except KeyError:
                return QVariant()
        return QVariant()
    
    def rowCount(self, index = QModelIndex()):
        return len(self.taginfo)
    
    def columnCount(self, index=QModelIndex()):
        return len(self.headerdata)
    
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index)|
                            Qt.ItemIsEditable| Qt.ItemIsDropEnabled)
    
    def setData(self, index, value, role = Qt.EditRole):
        """Sets the data of the currently edited cell as expected.
        Also writes tags and increases the undolevel."""
        
        if index.isValid() and 0 <= index.row() < len(self.taginfo):
            column = index.column()
            tag = self.headerdata[column][1]
            currentfile = self.taginfo[index.row()]
            #pdb.set_trace()
            filename = currentfile[FILENAME]
            newvalue = unicode(value.toString())
            #Tags that startwith "__" are usually read only except for __path
            #in which case we rename the files.
            if tag.startswith("__"):
                if tag == PATH:
                    try:
                        currentfile[FILENAME] = self.renameFile(index.row(), {PATH: newvalue})[FILENAME]
                    except IOError, detail:
                        #TODO: I would very much like for a tooltip to be displayed here saying that I can't write to the file.
                        return False
            else:
                what = audioinfo.Tag(filename)
                what.tags.update({tag: newvalue})
                try:
                    what.writetags()
                except IOError:
                    sys.stderr.write("Could not write to file " + filename + "\nDo you have write access?\n")
                    return False
                
            try:
                currentfile[self.undolevel] = {tag: currentfile[tag]}
            except KeyError:
                currentfile[self.undolevel] = {tag: ""}
            currentfile[tag] = newvalue
            self.undolevel += 1
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        index, index)
            return True
        return False
                                    
    def sort(self,column,order = Qt.DescendingOrder):
        tag = self.headerdata[column][1]
        for z in self.taginfo:
            if not z.has_key(tag): #We need every tag to have a value to sort with
                z[tag] = ""
        cmpfunc = compare()
        if order == Qt.AscendingOrder:
            self.taginfo = sorted(self.taginfo, cmpfunc.natcasecmp, itemgetter(tag))
        else:
            self.taginfo = sorted(self.taginfo, cmpfunc.natcasecmp, itemgetter(tag), True)
        self.reset()
    
    def setRowData(self,row,tags, undo = False, justrename = False):
        """A function to update one row.
        row is the row, tags is a dictionary of tags.
        
        If undo`is True, then an undo level is created for this file.
        If just rename is True, then (if tags contain a "__path" key) the files are just renamed.
        This speeds it up a lot.
        """

        if undo:
            oldtag = self.taginfo[row]
            oldtag = dict([(tag, oldtag[tag]) for tag in tags])
            if self.undolevel in self.taginfo[row]:
                self.taginfo[row][self.undolevel].update(oldtag)
            else:
                self.taginfo[row][self.undolevel] = oldtag
        
        self.taginfo[row].update(self.renameFile(row, tags))        
        
        if not justrename:
            what = audioinfo.Tag(self.taginfo[row][FILENAME])
            what.tags.update(tags)
            what.writetags()
            self.taginfo[row].update(tags)
            
        firstindex = self.index(row, 0)
        lastindex = self.index(row,self.columnCount() - 1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        firstindex, lastindex)
    
    def renameFile(self, row, tags):
        """If tags(a dictionary) contains a "__path" key, then the file
        in self.taginfo[row] is renamed based on that.
        
        If successful, tags is returned(with the new filename as a key)
        otherwise {} is returned."""        
        
        if PATH in tags:
            if os.path.splitext(tags[PATH])[1] == "":
                extension = os.path.extsep + self.taginfo[row]["__ext"]
            else:
                extension = ""
            oldfilename = self.taginfo[row][FILENAME]
            newfilename = path.join(path.dirname(oldfilename), safe_name(tags[PATH] + extension))
            try:
                os.rename(oldfilename, newfilename)            
            except IOError, detail:
                self.emit(SIGNAL('fileError'), self.taginfo[row])
                raise IOError, detail
            except OSError, detail:
                self.emit(SIGNAL('fileError'), self.taginfo[row])
                raise OSError, detail
                
            tags[FILENAME] = newfilename
        else:
            return {}
        return tags

        
    def removeRows(self, position, rows=1, index=QModelIndex(),showmsg = False, delfiles = True):
        """Please, only use this function to remove one row at a time. For some reason, it doesn't work
        too well on debian if more than one row is removed at a time."""
        self.beginRemoveRows(QModelIndex(), position,
                         position + rows -1)
        if showmsg == True:
            result = QMessageBox.question (None, "Delete files?", 
                    "Are you sure you want to delete the selected files?", 
                    "&Yes", "&No","", 1, 1)
            if result == 1:
                return False
        if delfiles == True:
            try:
                os.remove(self.taginfo[position][FILENAME])
            except OSError:
                QMessageBox.information(None,"Error", "I couldn't find the file :\n" + self.taginfo[position][FILENAME], QMessageBox.Ok)                
        del(self.taginfo[position])
        self.endRemoveRows()
        return True
 
    def setHeaderData(self, section, orientation, value, role = Qt.EditRole):
        if (orientation == Qt.Horizontal) and (role == Qt.DisplayRole):
            self.headerdata[section] = value
        self.emit(SIGNAL("headerDataChanged (Qt::Orientation,int,int)"), orientation, section, section)

    def insertColumns (self, column, count, parent = QModelIndex()):
        self.beginInsertColumns (parent, column, column + count -1)
        self.headerdata += [("","") for z in range(count - column)]
        self.endInsertColumns()
        return True

    def removeColumns(self, column, count, parent = QModelIndex()):
        """This function only allows removal of one column at a time.
        For some reason, it just clears the columns otherwise.
        So for now, this seems to work."""
        self.beginRemoveColumns(QModelIndex(), column , column + count - 1)
        del(self.headerdata[column])
        self.endRemoveColumns()
        return True    

class DelegateShit(QItemDelegate):
    def __init__(self,parent=None):
        QItemDelegate.__init__(self,parent)        
    
    def createEditor(self,parent,option,index):
            editor = QLineEdit(parent)
            editor.setFrame(False)
            self.connect(editor, SIGNAL("returnPressed()"),
                         self.commitAndCloseEditor)
            return editor
    
    def commitAndCloseEditor(self):
        editor = self.sender()
        if isinstance(editor, (QTextEdit, QLineEdit)):
            self.emit(SIGNAL("commitData(QWidget*)"), editor)
            self.emit(SIGNAL("closeEditor(QWidget*, QAbstractItemDelegate::EndEditHint)"), editor, QItemDelegate.EditNextItem)
            
    
    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.EditRole).toString()
        editor.setText(text)
    
    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.text()))

        
class TableShit(QTableView):
    """I need a more descriptive name for this.
    
    This table is the table that handles all my tags for me.
    The main functions and properties are:
    
    rowTags(row) -> Returns the tags from a row.
    updateRow(row, tags) - > Updates a row with the tags specified
    selectedRows -> A list of currently selected rows
    remRows() -> Removes the selected rows.
    playcommand -> Command to run to play files.
    """
    
    def __init__(self, headerdata = None, parent = None):
        QTableView.__init__(self,parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setAlternatingRowColors(True)
        

        self.tagmodel = TagModel(headerdata)
        self.setModel(self.tagmodel)
        delegate = DelegateShit(self)
        self.setItemDelegate(delegate)
        self.subFolders = False
        #For less typing and that the model doesn't have to be accessed directly
        self.updateRow = self.tagmodel.setRowData
    
    def selectedTags(self):
        """Retun a dictionary with the currently selected rows as keys.
        Each key contains a list with the selected columns of that row.
        
        {} is return if nothing is selected."""
        x = {}
        for z in self.selectedIndexes():
            try:
                x[z.row()].append(z.column())
            except KeyError:
                x[z.row()] = [z.column()]
        return x
        
    def selectionChanged(self, selected = None, deselected = None):
        """Pretty important. This updates self.selectedRows, which is used
        everywhere.
        
        I've set selected an deselected as None, because I sometimes
        want self.selectedRows updated without hassle."""
        
        selectedRows = set()
        selectedColumns = set()
        for z in self.selectedIndexes():
            selectedRows.add(z.row())
            selectedColumns.add(z.column())
        self.selectedRows = sorted(list(selectedRows))
        self.selectedColumns = sorted(list(selectedColumns))
        if selected is not None and deselected is not None:
            QTableView.selectionChanged(self, selected, deselected)
        self.emit(SIGNAL("itemSelectionChanged()"))
    
    def rowTags(self,row):
        """Returns all the tags pertinent to the file at row."""
        return self.model().taginfo[row]
    
    def dragEnterEvent(self, event):
        self.setAcceptDrops(True)
        event.accept()

    def dropEvent(self, event):
        #Unicode is really fucked up. Just drag and drop a file with unicode characters
        #and see what happens. I need some unicode education.
        files = [unicode(z.path()) for z in event.mimeData().urls()]
        #Usually the last element of files is an empty string.
        while '' in files:
            files.remove('')
        indexes = []
        for index, file in enumerate(files):
            if path.isdir(file):
                files.extend([path.join(file,z) for z in os.listdir(file)])
                indexes.append(index)
        for z in indexes:
            del(files[z])
        self.fillTable(files, True)
    
    def dragMoveEvent(self, event):
        if event.source() == self:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.accept()
    
    def mouseMoveEvent(self, event):
	
        if event.buttons() != Qt.LeftButton:
	       return
        mimeData = QMimeData()
        plainText = ""
        tags= []
        if hasattr(self, "selectedRows"):
            selectedRows = self.selectedRows
        else:
            return
        pnt = QPoint(*self.StartPosition)
        if (event.pos() - pnt).manhattanLength()  < QApplication.startDragDistance():
            return
        #I'm adding plaintext to MimeData
        #because XMMS doesn't seem to work well with Qt's URL's
        for z in selectedRows:
            plainText = plainText + os.path.join("file:///localhost", self.rowTags(z)[FILENAME]) + "\n"
            tags.append(QUrl(os.path.join("file:///localhost", self.rowTags(z)[FILENAME])))            
        mimeData = QMimeData()
        mimeData.setUrls(tags)
        mimeData.setText(plainText)
        
        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.setHotSpot(event.pos() - self.rect().topLeft())
        dropAction = drag.start(Qt.MoveAction | Qt.MoveAction)


    def mousePressEvent(self, event):
        QTableView.mousePressEvent(self, event)
        if event.buttons()  == Qt.RightButton:
            self.contextMenuEvent(event)
        if event.buttons() == Qt.LeftButton:
            self.StartPosition = [event.pos().x(), event.pos().y()]

        
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        play = menu.addAction("&Play Files")
        exttags = menu.addAction("E&xtended Tags")
        self.connect(play, SIGNAL('triggered()'), self.playFiles)
        self.connect(exttags, SIGNAL('triggered()'), self.editFile)
        menu.exec_(event.globalPos())
    
    def editFile(self):
        """Open window to edit all the tags in a file"""
        from helperwin import ExTags
        win = ExTags(self.model(), self.selectedRows[0], self)
        win.setModal(True)
        win.show()        
        
    def playFiles(self):
        """Play the selected files using the player specified in self.playcommand"""
        if self.selectedRows == []: return
        if hasattr(self, "playcommand"):
            li = copy(self.playcommand)
        else:
            li=["xmms"]
        for z in self.selectedRows:
            li.append(self.rowTags(z)[FILENAME])
        Popen(li)
    
    def setPlayCommand(self, command):
        self.playcommand = command
        
    def rowCount(self):
        return self.model().rowCount()
                
    def columnCount(self):
        return self.model().columnCount()
    
    def keyPressEvent(self, event):
        event.accept()
        if event.key() == Qt.Key_Delete and self.selectedRows is not None:
            result = QMessageBox.question (None, "Delete files?", 
                    "Are you sure you want to delete the selected files?", 
                    "&Yes", "&No","", 1, 1)
            if result == 0:
                self.remRows()
            return
        QTableView.keyPressEvent(self, event)
    
    def remRows(self):
        """Removes the currently selected rows
        and deletes the files."""
        if self.selectedRows == []: return
        self.model().removeRows(self.selectedRows[0], delfiles = True)
        self.selectionChanged()
        self.remRows()
    
    def fillTable(self, files, appendtags = False):
        """Fills the table with tags of the files specified in files.
        Files can be either a path(i.e a string) to a folder or a list of files.
        
        Nothing is returned since the results should be visible.
        
        If appendtags is True implies that files should just be appended to the table.
        
        If self.subFolders is True and files contains directory names
        then the files from this directory is added too.
        
        If self.subFolders is False and files is a list with just
        one item which happens to be a directory, then nothing will
        happen. Please convert it to a string first.
        """
        
        tag = audioinfo.Tag()
        tags = []
        self.dirname = None
        try:
            if (type(files) is str) or (type(files) is unicode):
                if path.isdir(files):
                    self.dirname = files
                    files = [path.join(files, z) for z in os.listdir(files)]
                else: 
                    files = [files]
        except OSError:
            sys.stderr.write("".join(["Couldn't access, ", folderpath, " do you have read access?\n"]))
        
        win = ProgressWin(self, len(files))
        
        def recursedir(folder):
            files = []
            for file in os.listdir(folder):
                if path.isdir(file):
                    files.extend(recursedir(path.join(folder,file)))
                else:
                    files.append(path.join(folder,file))
            return files
        
        if self.subFolders:
            [files.extend(recursedir(folder)) for folder in files if os.path.isdir(folder)]

        for file in files:            
            if win.wasCanceled(): break
            try:
                if tag.link(file) is not None:
                    tags.append(tag.tags.copy())
                    win.updateVal()
            except AttributeError:
                'This is raised if the file is an empty string.'
            except UnicodeDecodeError:
                sys.stderr.write("Couldn't open: " + file + " (UnicodeDecodeError)")
        self.model().load(tags, append = appendtags)
        win.close()
        #Select first item in the topleft corner
        if not appendtags:
            topLeft = self.model().index(0, 0);        
            selection = QItemSelection(topLeft, topLeft)
            self.selectionModel().select(selection, QItemSelectionModel.Select)
    
    def selectAll(self):
        model = self.model()
        topLeft = model.index(0, 0);
        bottomRight = model.index(model.rowCount()-1, model.columnCount()-1)
        
        selection = QItemSelection(topLeft, bottomRight);
        self.selectionModel().select(selection, QItemSelectionModel.Select)
    
    def invertSelection(self):
        model = self.model()
        topLeft = model.index(0, 0);
        bottomRight = model.index(model.rowCount()-1, model.columnCount()-1)
        
        selection = QItemSelection(topLeft, bottomRight);
        self.selectionModel().select(selection, QItemSelectionModel.Toggle)

    
    def reloadFiles(self):
        if self.dirname is not None:
            self.fillTable(self.dirname)
        else:
            self.fillTable([z[FILENAME] for z in self.model().taginfo])
