from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys,os 
import pdb
import audioinfo
from operator import itemgetter
from copy import copy

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
        
class modelshit(QAbstractTableModel):
    """The model used"""
    def __init__(self, headerdata, taginfo = {}):
        """Load tags. 
        
        headerdata must be a list of tuples
        where the first item is the displayrole and the second
        the tag to be used.
        
        taginfo should be a list of dictionaries
        where each dictionary represents a tag
        of a file.
        
        >>> headerdata = [("Artist", "artist"), ("Title", title")]
        >>> taginfo = [{"artist":"Gene Watson", "title": "Unknown"},
                        {"artist": "Keith Sweat", "title": "Nobody"}]
                        """
        QAbstractTableModel.__init__(self)
        self.headerdata=headerdata
        self.taginfo=taginfo
        self.reset()
        
    def load(self,taginfo,headerdata=None, append = False):
        """Loads tags as in __init__.
        If append is true, then the tags are just appended."""
        if headerdata is not None:
            self.headerdata=headerdata
        if append == True:
            self.taginfo.extend(taginfo)
        else:
            self.taginfo = taginfo
        self.reset()
        
        
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
            return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            return QVariant(self.headerdata[section][0])
        return QVariant(int(section + 1))
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or \
        not (0 <= index.row() < len(self.taginfo)):
            return QVariant()
        column = index.column()
        if (role == Qt.DisplayRole) or (role == Qt.ToolTipRole):
            try:
                return QVariant(self.taginfo[index.row()][self.headerdata[column][1]])
            except KeyError: return QVariant()
        return QVariant()
    
    def rowCount(self, index=QModelIndex()):
        return len(self.taginfo)
    
    def columnCount(self, index=QModelIndex()):
        return len(self.headerdata)
    
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index)|
                            Qt.ItemIsEditable)
    
    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and 0 <= index.row() < len(self.taginfo):
            column = index.column()
            tag = self.headerdata[column][1]
            filename = self.taginfo[index.row()]["__filename"]
            if tag.startswith("__"):
                return False
            else:
                what = audioinfo.Tag(filename)
                tagtowrite = {tag: unicode(value.toString())}
                #pdb.set_trace()
                what.tags = tagtowrite.copy()
                try:
                    what.writetags()
                except IOError:
                    QMessageBox.information(None,"Error", "Could not write to file " + filename, QMessageBox.Ok)
                    return False
                self.taginfo[index.row()][tag] = unicode(value.toString())
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                      index, index)
            return True
        return False
    
    def writeTag(self, row, tags):
        try:
            self.taginfo[row].update(tags)
        except TypeError:
            print "Can't update row", row
        what = audioinfo.Tag(self.taginfo[row]["__filename"])
        what.tags=tags
        what.writetags()
        
    
    def sort(self,column,order=Qt.DescendingOrder):
        tag = self.headerdata[column][1]
        for z in self.taginfo:
            if not z.has_key(tag): #We need every tag to have a value to sort with
                z[tag] = ""
        cmpfunc = compare()
        self.taginfo=sorted(self.taginfo, cmpfunc.natcasecmp, key = itemgetter(tag))
        self.reset()
    
    def setRowData(self,row,mydict):
        """A function to update one row
        row is the row, mydict is tag you want to set."""
        try:
            self.taginfo[row].update(mydict)
        except TypeError:
            print "Can't update row", row
        for z in mydict:
            column=0
            for y in self.headerdata:
                if y[1]==z:
                    what=self.createIndex(row,column)
                    self.setData(what,QVariant(mydict[y[1]]))
                column+=1
                
    def removeRows(self, position, rows=1, index=QModelIndex(),showmsg = False, delfiles = True):
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
                os.remove(self.taginfo[position]["__filename"])
            except OSError:
                QMessageBox.information(None,"Error", "I couldn't find the file :\n" + self.taginfo[position]["__filename"], QMessageBox.Ok)                
        del(self.taginfo[position])
        self.endRemoveRows()
        return True


class delegateshit(QItemDelegate):
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
        text = index.model().data(index, Qt.DisplayRole).toString()
        editor.setText(text)
    
    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.text()))

        
class TableShit(QTableView):
    def __init__(self,parent=None):
        QTableView.__init__(self,parent)
        self.setDragEnabled(True)
        
    def selectionChanged(self,what = None,shit = None):
        selectedRows=set()
        selectedColumns=set()
        for z in self.selectedIndexes():
            selectedRows.add(z.row())
            selectedColumns.add(z.column())
        self.selectedRows = list(selectedRows)
        self.selectedColumns = list(selectedColumns)
        self.emit(SIGNAL("itemSelectionChanged()"))
    
    def rowtags(self,row):
        #for column in range(len(what.headerdata)):
            #index=what.index(row,column)
            #mydict[what.headerdata[column]ementation does nothing and returns false.[1]]=unicode(what.data(index).toString())
        return self.model().taginfo[row]
    
    def updaterow(self,row,mydict):
        self.model().setRowData(row,mydict)
    
    def dragEnterEvent(self, event):
        event.accept()
        
    def dropEvent(self, event):
        pdb.set_trace()
        self.setText(event.mimeData()) 
    
    def mouseMoveEvent(self, event):
	
        if event.buttons() != Qt.LeftButton:
	       return

        mimeData = QMimeData()
        plainText = ""
        tags= []
        selectedRows = list(self.selectedRows)
        for z in selectedRows:
            plainText = plainText + os.path.join("file:///localhost", self.rowtags(z)["__filename"]) + "\n"
            tags.append(QUrl(os.path.join("file:///localhost", self.rowtags(z)["__filename"])))            
        mimeData = QMimeData()
        mimeData.setUrls(tags)
        mimeData.setText(plainText)
        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.setHotSpot(event.pos() - self.rect().topLeft())

        dropAction = drag.start(Qt.MoveAction | Qt.MoveAction)


    def mousePressEvent(self, event):
        QTableView.mousePressEvent(self, event)
        
    def keyPressEvent(self, event):
        event.accept()
        if event.key() == Qt.Key_Delete and self.selectedRows is not None:
            result = QMessageBox.question (None, "Delete files?", 
                    "Are you sure you want to delete the selected files?", 
                    "&Yes", "&No","", 1, 1)
            if result == 0:
                self.remrows(self.selectedRows)
            return
        QTableView.keyPressEvent(self, event)
    
    def remrows(self, selectedRows):
        if selectedRows == []: return
        self.model().removeRows(self.selectedRows[0], delfiles = True)
        self.selectionChanged()
        self.remrows(self.selectedRows)
            
#class mainwin(QWidget):
    #def __init__(self,parent=None):
        #QWidget.__init__(self,parent)
        #self.tableview = TableShit()
        #folder="/media/multi/StreetBeats Vol 1 - CD1"
        #tag=audioinfo.Tag()
        #myl=[]
        #for z in os.listdir(folder):
            #filename=os.path.join(folder,z)
            #tag.link(filename)
            #tag.gettags()
            #tag.tags["__filename"]=tag.info["filename"]
            #myl.append(tag.tags.copy())
        
        #header = self.tableview.horizontalHeader()
        #header.setSortIndicatorShown(True)
        #self.connect(header, SIGNAL("sectionClicked(int)"),
             #self.sortTable)
                        
        #self.model = modelshit([("Artist","artist"),("Title","title"),("Album","album")],myl)
        #self.tableview.setModel(self.model)
        
        #grid=QGridLayout()
        #grid.addWidget(self.tableview,0,0)
        #self.setLayout(grid)
        #what=delegateshit(self)
        #self.tableview.setItemDelegate(what)
        #self.tableview.setDropIndicatorShown(True)
        #self.resize(500,500)
        #self.connect(self.tableview,SIGNAL("itemSelectionChanged()"),self.shitty)
    
    #def shitty(self):
        #self.tableview.model().setRowData(2,{"artist":"Keith the Great","title":"Fcuk"})
                
        
    #def sortTable(self,val):
        #self.tableview.sortByColumn(val)
        #self.setFocus()
    
    
        
#app=QApplication(sys.argv)
#qb=mainwin()
#qb.show()
#app.exec_()



    

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        