#tagmodel.py

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
import sys,os, audioinfo, resource
from operator import itemgetter
from copy import copy, deepcopy
from subprocess import Popen
from os import path
from audioinfo import PATH, FILENAME, usertags
from puddleobjects import unique, safe_name, partial, compare, ProgressWin, PuddleThread
from musiclib import MusicLibError
import time
from errno import EEXIST

SETDATAERROR = SIGNAL("setDataError")
LIBRARY = '__library'
ENABLEUNDO = SIGNAL('enableUndo')

class TagModel(QAbstractTableModel):
    """The model used in TableShit
    Methods you shoud take not of are(read docstrings for more):

    setData -> As per the usual model, can only write one tag at a time.
    setRowData -> Writes a row's tags at once.
    undo -> undo's changes
    setTestData and unSetTestData -> Used to display temporary values in the table.
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
        self.colorRows = []
        self.sortOrder = (0, Qt.AscendingOrder)
        if taginfo is not None:
            self.taginfo = unique(taginfo)
            self.sort(*self.sortOrder)
        else:
            self.taginfo = []
            self.reset()
        self.undolevel = 0
        self.testData = {}

    def _getUndoLevel(self):
        return self._undolevel

    def _setUndoLevel(self, value):
        if value == 0:
            self.emit(ENABLEUNDO, False)
        else:
            self.emit(ENABLEUNDO, True)
        self._undolevel = value

    undolevel = property(_getUndoLevel, _setUndoLevel)

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
        oldfiles =  []
        newfiles = []
        rows = []
        for row, file in enumerate(self.taginfo):
            if level in file:
                if LIBRARY in file:
                    oldfiles.append(file.tags.copy())
                self.setRowData(row, file[level])
                rows.append(row)
                del(file[level])
                if LIBRARY in file:
                    newfiles.append(file.tags.copy())
        if rows:
            self.updateTable(rows)
            if oldfiles:
                self.emit(SIGNAL('libFileChanged'), oldfiles, newfiles)
        if self.undolevel > 0:
            self.undolevel -= 1

    def load(self,taginfo,headerdata=None, append = False):
        """Loads tags as in __init__.
        If append is true, then the tags are just appended."""
        if headerdata is not None:
            self.headerdata = headerdata
        if append:
            self.taginfo.extend(taginfo)
        else:
            self.taginfo = taginfo
            self.undolevel = 0
        self.taginfo = unique(self.taginfo)
        self.sort(*self.sortOrder)

    def reset(self):
        #Sometimes, (actually all the time on my box, but it may be different on yours)
        #if a number files loaded into the model is equal to number
        #of files currently in the model then the TableView isn't updated.
        #Why the fuck I don't know, but this signal, intercepted by the table,
        #updates the view and make everything work okay.
        self.emit(SIGNAL('modelReset'))
        QAbstractTableModel.reset(self)

    def changeFolder(self, olddir, newdir):
        """Used for changing the directory of all the files in olddir to newdir.
        i.e. All children of olddir will now become children of newdir

        No *actual* moving is done though."""

        folder = itemgetter('__folder')
        tags = [z for z in self.taginfo if folder(z).startswith(olddir)]
        libtags = []
        for audio in tags:
            if folder(audio) == olddir:
                audio[FILENAME] = path.join(newdir, audio[PATH])
                audio['__folder'] = newdir
            else: #Newdir is a parent
                audio['__folder'] = newdir + folder(audio)[len(olddir):]
                audio[FILENAME] = path.join(folder(audio), audio[PATH])
            if '__library' in audio:
                    audio.save(True)
        self.reset()

    def columnCount(self, index=QModelIndex()):
        return len(self.headerdata)

    def rowCount(self, index = QModelIndex()):
        return len(self.taginfo)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.taginfo)):
            return QVariant()
        if (role == Qt.DisplayRole) or (role == Qt.ToolTipRole) or (role == Qt.EditRole):
            try:
                val = self.taginfo[index.row()][self.headerdata[index.column()][1]]
                if type(val) is unicode or type(val) is str:
                    return QVariant(val)
                else:
                    return QVariant(val[0])
            except (KeyError, IndexError), detail:
                return QVariant()
        elif role == Qt.BackgroundColorRole:
            if index.row() in self.colorRows:
                return QVariant(QColor(Qt.green))
        return QVariant()

    def setData(self, index, value, role = Qt.EditRole):
        """Sets the data of the currently edited cell as expected.
        Also writes tags and increases the undolevel."""

        if index.isValid() and 0 <= index.row() < len(self.taginfo):
            column = index.column()
            tag = self.headerdata[column][1]
            currentfile = self.taginfo[index.row()]

            filename = currentfile[FILENAME]
            newvalue = unicode(value.toString())
            #Tags that startwith "__" are usually read only except for __path
            #in which case we rename the files.
            try:
                oldvalue = deepcopy(currentfile[tag])
            except KeyError:
                oldvalue = [""]

            if tag.startswith("__"):
                if tag == PATH:
                    try:
                        currentfile[FILENAME] = self.renameFile(index.row(), {PATH: newvalue})[FILENAME]
                    except (IOError, OSError), detail:
                        self.emit(SETDATAERROR, index.row(), column, "Couldn't rename " + filename + ": " + detail.strerror)
                        return False
                else:
                    return False #Editing read-only values
            try:
                currentfile[tag] = newvalue
                currentfile.save()
            except (IOError, OSError), detail:
                currentfile[tag] = oldvalue
                self.emit(SETDATAERROR, index.row(), column, "Couldn't write to " + filename + ": " + detail.strerror)
                return False

            currentfile[self.undolevel] = {tag: oldvalue}
            self.emit(SIGNAL('fileChanged()'))
            if LIBRARY in currentfile:
                oldfile = currentfile.tags.copy()
                oldfile.update(currentfile[self.undolevel])
                self.emit(SIGNAL('libFileChanged'), [oldfile], [currentfile])
            self.undolevel += 1
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        index, index)
            return True
        return False

    def setRowData(self,row,tags, undo = False, justrename = False):
        """A function to update one row.
        row is the row, tags is a dictionary of tags.

        If undo`is True, then an undo level is created for this file.
        If justrename is True, then (if tags contain a "__path" key) the file is just renamed.
        i.e not tags are written.
        """

        currentfile = self.taginfo[row]
        if undo:
            oldtag = currentfile
            oldtag = dict([(tag, oldtag[tag]) for tag in set(oldtag).intersection(tags)])
            if self.undolevel in oldtag:
                currentfile[self.undolevel].update(oldtag)
            else:
                currentfile[self.undolevel] = oldtag
        if '__image' in tags:
            if not hasattr(currentfile, 'image'):
                del(tags['__image'])
            else:
                images = []
                for z in tags['__image']:
                    images.append(dict([(key,val) for key,val in z.items() if key in audioinfo.IMAGETAGS]))
                tags['__image'] = [currentfile.image(**z) for z in images]
        currentfile.update(self.renameFile(row, tags))
        if justrename and LIBRARY in currentfile:
            currentfile.save(True)
        if not justrename:
            try:
                currentfile.update(tags)
                currentfile.save()
            except (OSError, IOError), detail:
                currentfile.update(currentfile[self.undolevel])
                del(currentfile[self.undolevel])
                raise detail

    def updateTable(self, rows):
        firstindex = self.index(min(rows), 0)
        lastindex = self.index(max(rows),self.columnCount() - 1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        firstindex, lastindex)


    def dropMimeData(self, data, action, row, column, parent = QModelIndex()):
        return True

    def supportedDropActions(self):
        return Qt.CopyAction

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index)|
                            Qt.ItemIsEditable| Qt.ItemIsDropEnabled)

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

    def insertColumns (self, column, count, parent = QModelIndex()):
        self.beginInsertColumns (parent, column, column + count -1)
        self.headerdata += [("","") for z in range(count - column)]
        self.endInsertColumns()
        self.emit(SIGNAL('modelReset')) #Because of the strange behaviour mentioned in reset.
        return True

    def removeColumns(self, column, count, parent = QModelIndex()):
        """This function only allows removal of one column at a time.
        For some reason, it just clears the columns otherwise.
        So for now, this seems to work."""
        self.beginRemoveColumns(QModelIndex(), column , column + count - 1)
        del(self.headerdata[column])
        self.endRemoveColumns()
        return True


    def removeRows(self, position, rows=1, index=QModelIndex(), delfiles = True, msgparent = None):
        """Please, only use this function to remove one row at a time. For some reason, it doesn't work
        too well on debian if more than one row is removed at a time."""
        self.beginRemoveRows(QModelIndex(), position,
                         position + rows -1)
        if delfiles:
            audio = self.taginfo[position]
            os.remove(audio[FILENAME])
            if LIBRARY in audio:
                self.emit(SIGNAL('delLibFile'), [audio])
        del(self.taginfo[position])
        self.endRemoveRows()
        return True

    def renameFile(self, row, tags):
        """If tags(a dictionary) contains a "__path" key, then the file
        in self.taginfo[row] is renamed based on that.

        If successful, tags is returned(with the new filename as a key)
        otherwise {} is returned."""

        if PATH in tags:
            if path.splitext(tags[PATH])[1] == "":
                extension = path.extsep + self.taginfo[row]["__ext"]
            else:
                extension = ""
            oldfilename = self.taginfo[row][FILENAME]
            newfilename = path.join(path.dirname(oldfilename), safe_name(tags[PATH] + extension))
            try:
                if os.path.exists(newfilename) and newfilename != oldfilename:
                    raise IOError(EEXIST, os.strerror(EEXIST), oldfilename)
                os.rename(oldfilename, newfilename)
            #I don't want to handle the error, but at the same time I want to know
            #which file the error occured at.
            except (IOError, OSError), detail:
                self.emit(SIGNAL('fileError'), self.taginfo[row])
                raise detail
            tags[FILENAME] = newfilename
        else:
            return {}
        return tags

    def rowColors(self, rows = None):
        """Changes the background of rows to green.

        If rows is None, then the background of all the rows in the table
        are returned to normal."""
        if not rows:
            if self.colorRows:
                firstindex = self.index(self.colorRows[0], 0)
                lastindex = self.index(self.colorRows[-1], self.columnCount() - 1)
            else:
                firstindex = self.index(0, 0)
                lastindex = self.index(0, self.columnCount() - 1)
            self.colorRows = []
        else:
            if self.colorRows:
                if min(self.colorRows) <= min(rows):
                    firstrow = min(self.colorRows)
                else:
                    firstrow = min(rows)
                if max(self.colorRows) <= max(rows):
                    lastrow = max(self.colorRows)
                else:
                    lastrow = max(rows)
                self.colorRows = rows
            else:
                firstrow = min(rows)
                lastrow = max(rows)
                self.colorRows = rows
            firstindex = self.index(firstrow, 0)
            lastindex = self.index(lastrow, self.columnCount() - 1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        firstindex, lastindex)

    def setHeaderData(self, section, orientation, value, role = Qt.EditRole):
        if (orientation == Qt.Horizontal) and (role == Qt.DisplayRole):
            self.headerdata[section] = value
        self.emit(SIGNAL("headerDataChanged (Qt::Orientation,int,int)"), orientation, section, section)


    def setTestData(self, rows, tags):
        """A method that allows you to change the visible data of
        the model without writing tags.

        rows is the rows that you want to change
        tags -> is the tags that are to be shown.

        If you want want to write the values that you showed
        call unsetData with write = True.

        However, if you just want to return to the previous
        view, call unsetData with write = False, and if you want,
        the rows you want to return to normal.

        Note, that if the user changed anything during this
        process, then those changes are left alone."""

        unsetrows = [row for row in rows if row in self.testData][len(tags):]
        if unsetrows:
            self.unSetTestData(rows = unsetrows)
        for row, tag in zip(rows, tags):
            if row in self.testData:
                self.testData[row][1] = tag
            else:
                self.testData[row] = [self.taginfo[row].copy(), tag]
            self.taginfo[row].update(tag)
        firstindex = self.index(min(rows), 0)
        lastindex = self.index(max(rows),self.columnCount() - 1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        firstindex, lastindex)

    def unSetTestData(self, write = False, rows = None):
        """See testData"""
        def getdiff(tag1, tag2):
            undolevel = [z for z in tag1 if type(z) is int]
            if undolevel: undolevel = max(undolevel)
            oldundolevel = [z for z in tag2 if type(z) is int]
            if oldundolevel: oldundolevel = max(oldundolevel)
            if oldundolevel != undolevel:
                return True
            else:
                return False

        if not self.testData:
            return

        if write:
            for row, tag in self.testData.items():
                oldtag = tag[0]
                newtag = tag[1]
                if getdiff(oldtag, self.taginfo[row]):
                    newtag = [dict([(z,newtag[z])]) for z in newtag if
                            (z in oldtag[z]) and (z in self.taginfo[row])
                            and oldtag[z] == self.taginfo[row][z]]
                self.setRowData(row, newtag, True)
            self.undolevel += 1
            rows = self.testData.keys()
            self.testData = {}
            self.emit(ENABLEUNDO, True)
        else:
            if rows is not None:
                for row in [row for row in rows if row in self.testData]:
                    tag = self.testData[row]
                    if not getdiff(self.taginfo[row], tag[1]):
                        self.taginfo[row] = tag[0].copy()
                    del(self.testData[row])
            else:
                rows = self.testData.keys()
                for row, tag in self.testData.items():
                    oldtag = tag[0]
                    newtag = tag[1]
                    if not getdiff(self.taginfo[row], newtag):
                        self.taginfo[row] = oldtag
                    del(self.testData[row])
                self.emit(ENABLEUNDO, True)

        firstindex = self.index(min(rows), 0)
        lastindex = self.index(max(rows), self.columnCount() - 1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        firstindex, lastindex)

    def sort(self,column, order = Qt.DescendingOrder):
        self.sortOrder = (column, order)
        tag = self.headerdata[column][1]
        cmpfunc = compare().natcasecmp
        if order == Qt.AscendingOrder:
            self.taginfo = sorted(self.taginfo, cmpfunc, itemgetter(tag))
        else:
            self.taginfo = sorted(self.taginfo, cmpfunc, itemgetter(tag), True)
        self.reset()

class TagDelegate(QItemDelegate):
    def __init__(self,parent=None):
        QItemDelegate.__init__(self,parent)

    def createEditor(self,parent,option,index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.installEventFilter(self)
        return editor

    def keyPressEvent(self, event):
        QItemDelegate.keyPressEvent(self, event)

    def commitAndCloseEditor(self):
        editor = self.sender()
        self.emit(SIGNAL("closeEditor(QWidget*, QAbstractItemDelegate::EndEditHint)"), editor, QItemDelegate.EditNextItem)

    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.EditRole).toString()
        editor.setText(text)

    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.text()))



class TagTable(QTableView):
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
        self.showmsg = True
        self._currentcol = {}
        self._currentrow = {}

        self.tagmodel = TagModel(headerdata)
        self.setModel(self.tagmodel)
        delegate = TagDelegate(self)
        self.setItemDelegate(delegate)
        self.subFolders = False

        self.play = QAction("&Play", self)
        self.play.setShortcut('Ctrl+p')
        self.exttags = QAction("E&xtended Tags", self)
        self.delete = QAction(QIcon(':/remove.png'), '&Delete', self)
        self.delete.setShortcut('Delete')

        connect = lambda a,f: self.connect(a, SIGNAL('triggered()'), f)

        connect(self.play, self.playFiles)
        connect(self.exttags, self.editFile)
        connect(self.delete, self.deleteSelected)

        separator = QAction(self)
        separator.setSeparator(True)

        self.actions = [self.play, self.exttags, separator, self.delete]

    def columnCount(self):
        return self.model().columnCount()

    def rowCount(self):
        return self.model().rowCount()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        [menu.addAction(z) for z in self.actions]
        menu.exec_(event.globalPos())

    def _isEmpty(self):
        if self.model().rowCount() == 0:
            return True
        return False

    isempty = property(_isEmpty)

    def deleteSelected(self):
        #filenames = [self.rowTags(z)[FILENAME] for z in self.selectedRows]
        #msg = '<br />'.join(filenames)
        result = QMessageBox.question (self, "puddletag",
                    "Are you sure you want to delete the selected files?",
                    "&Yes", "&No","", 1, 1)
        if result == 0:
            showmessage = True
            selectedRows = sorted(self.selectedRows)
            temprows = copy(selectedRows)
            for i,row in enumerate(selectedRows):
                try:
                    self.model().removeRows(temprows[i], msgparent = self)
                    temprows = [z - 1 for z in temprows]
                except (OSError, IOError), detail:
                    filename = self.rowTags(row)[FILENAME]
                    if len(selectedRows) > 1:
                        if showmessage:
                            errormsg = u"I couldn't delete <b>%s</b> (%s)<br /> Do you want to continue?" % \
                                        (filename, detail.strerror)
                            mb = QMessageBox('Error', errormsg, QMessageBox.Warning, QMessageBox.Yes or QMessageBox.Default,
                                    QMessageBox.No or QMessageBox.Escape, QMessageBox.YesAll, self )
                            ret = mb.exec_()
                            if ret == QMessageBox.No:
                                break
                            elif ret == QMessageBox.YesAll:
                                showmessage = False
                    else:
                        QMessageBox.critical(self,"Error", u"I couldn't delete the file <b>%s</b> (%s)" % \
                                            (filename, detail.strerror), QMessageBox.Ok, QMessageBox.NoButton)
            self.selectionChanged()

    def dragEnterEvent(self, event):
        self.setAcceptDrops(True)
        event.accept()

    def dropEvent(self, event):
        files = [unicode(z.path()) for z in event.mimeData().urls()]
        for index, audio in enumerate(files):
            if path.isdir(audio):
                files.extend([path.join(audio,z) for z in os.listdir(audio)])
                files[index] = ""

        while '' in files:
            files.remove('')
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
            plainText = plainText + path.join("file:///localhost", self.rowTags(z)[FILENAME]) + "\n"
            tags.append(QUrl(path.join("file:///localhost", self.rowTags(z)[FILENAME])))
        mimeData = QMimeData()
        mimeData.setUrls(tags)
        mimeData.setText(plainText)

        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.setHotSpot(event.pos() - self.rect().topLeft())
        drag.start(Qt.MoveAction)

    def mousePressEvent(self, event):
        QTableView.mousePressEvent(self, event)
        if event.buttons()  == Qt.RightButton:
            self.contextMenuEvent(event)
        if event.buttons() == Qt.LeftButton:
            self.StartPosition = [event.pos().x(), event.pos().y()]

    def editFile(self):
        """Open window to edit all the tags in a file"""
        from helperwin import ExTags
        win = ExTags(self.model(), self.selectedRows[0], self)
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL("tagChanged()"), self.selectionChanged)

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
        self.time = time.time()
        self.dirname = None
        self.selectedRows = []
        self.selectedColumns = []
        try:
            if isinstance(files, basestring):
                if path.isdir(files):
                    self.dirname = files
                    files = [path.join(files, z) for z in os.listdir(files)]
                else:
                    files = [files]
        except (IOError, OSError), detail:
            sys.stderr.write("".join([u"Couldn't read, ", files, u":" + unicode(detail.strerror)]))

        win = ProgressWin(self, len(files), 'Reading ')
        win.show()

        def recursedir(folder):
            #Not sure (cause I just discovered it), but os.walk would be more complicated.
            files = []
            try:
                for audio in os.listdir(folder):
                    if path.isdir(audio):
                        files.extend(recursedir(path.join(folder,audio)))
                    else:
                        files.append(path.join(folder,audio))
            except (OSError, IOError):
                "Don't want to stop on account of not having permission."
            return files

        if self.subFolders:
            [files.extend(recursedir(folder)) for folder in files if path.isdir(folder)]

        def tempfunc():
            tags = []
            for i, audio in enumerate(files):
                if win.wasCanceled: break
                try:
                    tag = audioinfo.Tag(audio)
                    if tag:
                        tags.append(tag)
                except IOError, OSError:
                    pass
                except Exception, e:
                    print unicode(e)
                self.emit(SIGNAL('updateProgress(int)'), i)
            return tags

        self.t = PuddleThread(tempfunc)
        self.connect(self, SIGNAL('updateProgress(int)'), win.setValue)
        self._appfill = partial(self._fillTable, [win, appendtags])
        self.connect(self.t, SIGNAL('finished()'), self._appfill)
        self.t.start()

    def _fillTable(self, temp):
        win = temp[0]
        appendtags = temp[1]
        win.close()
        tags = self.t.retval
        if tags:
            [self.showRow(z) for z in xrange(self.rowCount())] #The table gets all fucked up if any rows are hidden.
        self.model().load(tags, append = appendtags)
        #Select first item in the topleft corner
        if not appendtags:
            topLeft = self.model().index(0, 0)
            selection = QItemSelection(topLeft, topLeft)
            self.selectionModel().select(selection, QItemSelectionModel.Select)
        print time.time() - self.time

    def invertSelection(self):
        model = self.model()
        topLeft = model.index(0, 0);
        bottomRight = model.index(model.rowCount()-1, model.columnCount()-1)

        selection = QItemSelection(topLeft, bottomRight);
        self.selectionModel().select(selection, QItemSelectionModel.Toggle)

    def keyPressEvent(self, event):
        event.accept()
        #You might think that this is redunndant since a delete
        #action is defined in contextMenuEvent, but if this isn't
        #done then the delegate is entered.
        if event.key() == Qt.Key_Delete and self.selectedRows:
            self.deleteSelected()
            return
        #This is so that an item isn't edited when the user's holding the shift or
        #control key.
        elif event.key() == Qt.Key_Space and (Qt.ControlModifier == event.modifiers() or Qt.ShiftModifier == event.modifiers()):
            self.setEditTriggers(self.NoEditTriggers)
            QTableView.keyPressEvent(self, event)
            self.setEditTriggers(self.AnyKeyPressed)
            return
        QTableView.keyPressEvent(self, event)

    def playFiles(self):
        """Play the selected files using the player specified in self.playcommand"""
        if not self.selectedRows: return
        if hasattr(self, "playcommand"):
            if self.playcommand is True:
                li = [QUrl(path.join("file:///localhost", self.rowTags(z)[FILENAME])) for z in self.selectedRows]
                QDesktopServices.openUrl(li)
            else:
                li = copy(self.playcommand)
                li.extend([self.rowTags(z)[FILENAME] for z in self.selectedRows])
                try:
                    Popen(li)
                except (OSError), detail:
                    if detail.errno != 2:
                        QMessageBox.critical(self,"Error", u"I couldn't play the selected files: (<b>%s</b>) <br />Does the music player you defined (<b>%s</b>) exist?" % \
                                            (detail.strerror, u" ".join(self.playcommand)), QMessageBox.Ok, QMessageBox.NoButton)
                    else:
                        QMessageBox.critical(self,"Error", u"I couldn't play the selected files, because the music player you defined (<b>%s</b>) does not exist." \
                                            % u" ".join(self.playcommand), QMessageBox.Ok, QMessageBox.NoButton)

    def reloadFiles(self):
        if self.dirname is not None:
            self.fillTable(self.dirname)
        else:
            self.fillTable([z[FILENAME] for z in self.model().taginfo])
        self.selectCorner()

    def rowTags(self,row, stringtags = False):
        """Returns all the tags pertinent to the file at row."""
        if stringtags:
            return self.model().taginfo[row].stringtags()
        return self.model().taginfo[row]

    def selectCurrentColumn(self):
        if self.selectedIndexes():
            col = self.selectedIndexes()[0].column()
            model = self.model()
            topLeft = model.index(0, col)
            bottomRight = model.index(model.rowCount()-1, col)

            selection = QItemSelection(topLeft, bottomRight);
            self.selectionModel().select(selection, QItemSelectionModel.Select)

    def selectAll(self):
        model = self.model()
        topLeft = model.index(0, 0);
        bottomRight = model.index(model.rowCount()-1, model.columnCount()-1)

        selection = QItemSelection(topLeft, bottomRight);
        self.selectionModel().select(selection, QItemSelectionModel.Select)


    def selectCorner(self):
        topLeft = self.model().index(0, 0)
        selection = QItemSelection(topLeft, topLeft)
        self.selectionModel().select(selection, QItemSelectionModel.Select)
        self.setFocus()

    def setModel(self, model):
        QTableView.setModel(self, model)
        #For less typing and that the model doesn't have to be accessed directly
        self.updateRow = model.setRowData
        self.connect(model, SIGNAL('modelReset'), self.selectCorner)
        self.connect(model, SIGNAL('setDataError'), self.showTool)
        self.connect(model, SIGNAL('fileChanged()'), self.selectionChanged)

    def currentRowSelection(self):
        """Returns a dictionary with the currently selected rows as keys.
        Each key contains a list with the selected columns of that row.

        {} is returned if nothing is selected."""
        x = {}
        for z in self.selectedIndexes():
            try:
                x[z.row()].append(z.column())
            except KeyError:
                x[z.row()] = [z.column()]
        return x

    def currentColumnSelection(self):
        x = {}
        for z in self.selectedIndexes():
            try:
                x[z.column()].append(z.row())
            except KeyError:
                x[z.column()] = [z.row()]
        return x

    def _selectedTags(self):
        rowTags = self.rowTags
        return [rowTags(row) for row in self.selectedRows]

    selectedTags = property(_selectedTags)

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
        self.emit(SIGNAL('itemSelectionChanged()'))

    def saveCurrent(self):
        self._currentcol = self.currentColumnSelection()
        self._currentrow = self.currentRowSelection()

    def setHorizontalHeader(self, header):
        QTableView.setHorizontalHeader(self, header)
        self.connect(header,
                            SIGNAL('saveSelection'), self.saveCurrent)

    def showTool(self, row, column, text):
        """Shows a tooltip when an error occors.

        Actually, a tooltip is never shown, because the table
        is updated as soon as it tries to show. So a setDataError
        signal is emitted with the text, than can be used to show
        text in the status bar or something."""
        y = -self.mapFromGlobal(self.pos()).y() + self.rowViewportPosition(row)
        x = -self.mapFromGlobal(self.pos()).x() + self.columnViewportPosition(column)
        QToolTip.showText(QPoint(x,y), text)
        self.emit(SIGNAL('setDataError'), text)

    def setPlayCommand(self, command):
        self.playcommand = command


    def sortByColumn(self, column):
        """Guess"""

        currentrow = self._currentrow
        currentcol = self._currentcol


        if not currentrow:
            QTableView.sortByColumn(self, column)
            return

        def getGroups(rows):
            groups = []
            last = [rows[0]]
            for row in rows[1:]:
                if row - 1 == last[-1]:
                    last.append(row)
                else:
                    groups.append(last)
                    last = [row]
            groups.append(last)
            return groups

        try:
            tags = [(self.rowTags(row), row) for row in currentrow]
        except IndexError:
            tags = []

        QTableView.sortByColumn(self, column)

        getrow = self.model().taginfo.index
        modelindex = self.model().index
        selection = QItemSelection()
        select = lambda top, low, col: selection.append(
                        QItemSelectionRange(modelindex(top, col),
                                                    modelindex(low, col)))

        new = dict([(row, getrow(tag)) for tag, row in tags])

        groups = {}
        for col, rows in currentcol.items():
            groups[col] = getGroups(sorted([new[row] for row in rows]))

        for col, rows in groups.items():
            [select(min(row), max(row), col) for row in rows]
        self.selectionModel().select(selection, QItemSelectionModel.Select)