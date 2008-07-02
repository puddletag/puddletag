from PyQt4 import QtGui,QtCore
import sys, audioinfo,os, copy
from subprocess import Popen
import pdb,abstract
import findfunc
from os import path

class ProgressWin(QtGui.QProgressDialog):
    def __init__(self, parent=None, maximum = 100):
        QtGui.QProgressDialog.__init__(self, "", "Cancel", 0, maximum, parent)
        self.setModal(True)
        self.setWindowTitle("Please Wait...")
        #self.forceShow()
    
    def updateVal(self):
        self.setValue(self.value() + 1)

class FrameCombo(QtGui.QGroupBox):
    """FrameCombo(self,tags,parent=None)
    
    Hold the combos that allow you to edit
    tags individually if so inclined.
    
    Tags should be a list with the tags 
    that each combo box should hold specified
    in the form [(Display Value, internal tag)]
    .e.g [("Artist","artist"), ("Track Number", "track")]
    """
    
    def __init__(self,tags,parent=None):
        QtGui.QGroupBox.__init__(self,parent)

        grid = QtGui.QGridLayout()
        
        self.combos = {}
        grid = QtGui.QGridLayout()
        
        j = 0
        for tag in tags:
            tagval = tag[1]
            grid.addWidget(QtGui.QLabel(tag[0]), j, 0)
            self.combos[tagval] = QtGui.QComboBox()
            self.combos[tagval].setInsertPolicy(QtGui.QComboBox.NoInsert)
            grid.addWidget(self.combos[tagval], j+1, 0)
            j = j + 2

        self.setLayout(grid)
    
    def disableCombos(self):
        for z in self.combos:
            self.combos[z].clear()
            self.combos[z].setEnabled(False)


class DirView(QtGui.QTreeView):
    """The treeview sude to select a directory.
    This class was created only to allow the itemselectionChanged
    signal to be emitted."""
    def __init__(self,parent = None):
        QtGui.QTreeView.__init__(self,parent)
        self.setAcceptDrops(False)
    
    def selectionChanged(self,selected,deselected):
        self.emit(QtCore.SIGNAL("itemSelectionChanged()"))
    
    def contextMenuEvent(self, event):
        menu = QtGui.QMenu(self)
        twoAction = menu.addAction("&Add Folder")
        self.connect(twoAction,QtCore.SIGNAL('triggered()'),self.what)
        menu.exec_(event.globalPos())

    def what(self):
        self.emit(QtCore.SIGNAL("addFolder", self.model().filePath(self.selectedIndexes()[0])))


class TableWindow(QtGui.QWidget):
    def __init__(self,parent=None):
        QtGui.QWidget.__init__(self,parent)
        self.resize(1000,800)
        
        self.table = abstract.TableShit(self)
        self.headerdata = ([("Path", "__path"), ("Artist", "artist"), 
                            ("Title", "title"), ("Album", "album"), \
                            ("BitRate", "__bitrate"), ("Length","__length")])
        self.tablemodel = abstract.modelshit(self.headerdata)
        delegate = abstract.delegateshit(self)
        self.table.setItemDelegate(delegate)
        self.table.setModel(self.tablemodel)
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        
        self.combogroup = FrameCombo(self.headerdata[1:] + [("Year","date")], self)
        self.combogroup.setMaximumWidth(300)
        self.combogroup.setMinimumSize(300,300)
        
        self.dirmodel = QtGui.QDirModel()
        self.dirmodel.setSorting(QtCore.QDir.IgnoreCase)
        self.dirmodel.setFilter(QtCore.QDir.AllDirs)
        self.dirmodel.setReadOnly(False)
        
        self.tree = DirView()
        self.tree.setModel(self.dirmodel)
        self.tree.setMaximumWidth(300)
        self.tree.setMinimumSize(300,300)
        [self.tree.hideColumn(column) for column in range(1,4)]
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        
        grid = QtGui.QGridLayout()
        grid.addWidget(self.combogroup,0,0)
        grid.setColumnMinimumWidth(0,300)
        grid.addWidget(self.tree,1,0)
        grid.addWidget(self.table,0,1,2,1)
        self.setLayout(grid)

        self.connect(self.table, QtCore.SIGNAL('itemSelectionChanged()'),
                                         self.fillcombos)       
        self.connect(header, QtCore.SIGNAL("sectionClicked(int)"),
             self.sorttable)
        
        i = 0
        for z in [238, 202, 243, 203, 54]:
            self.table.setColumnWidth(i, z)
            i += 1
        
    def sorttable(self,val):
        self.table.sortByColumn(val)
        #This is due to the odd behaviour of the table
        self.setFocus()
    
    def fillcombos(self):
        """Fills the QComboBoxes in FrameCombo with
        the tags selected from self.table. It also adds
        two items, <keep> and <blank>. If <keep> is selected
        and the tags in the combos are saved, then they remain unchanged.
        If <blank> is selected, then the tag is removed"""
        
        #import time
        #print "run"
        #print time.strftime("%H : %M : %S")
        combos = self.combogroup.combos
        
        for combo in self.combogroup.combos:
            combos[combo].clear()
            combos[combo].setEditable(True)
            combos[combo].addItems(["<keep>", "<blank>"])
            combos[combo].setEnabled(False)
        
        mydict={}
        
        #Removes all duplicate entries for the combos
        #by adding them to a set.
        for row in self.table.selectedRows:
            taginfo=self.table.rowtags(row)
            for tag in taginfo:
                try:
                    mydict[tag].add(taginfo[tag])
                except KeyError:
                    mydict[tag]=set()
                    mydict[tag].add(taginfo[tag])
        
        #Add values to combos
        for tagset in mydict:
            [combos[tagset].addItem(unicode(z)) for z in sorted(mydict[tagset])
                    if combos.has_key(tagset)]
                                        

        for combo in combos:
            combos[combo].setEnabled(True)
            if combos[combo].count()>3: 
                combos[combo].setCurrentIndex(0)
            else: 
                combos[combo].setCurrentIndex(2)
                        
        #print time.strftime("%H : %M : %S")
        
    def filltable(self,folderpath, appendtags = False):
        """Fills self.table with the tags as retrieved from the
        directory folderpath."""
        
        #import time
        #print folderpath
        #print time.strftime("%H : %M : %S")
        tag=audioinfo.Tag()
        tags=[]
        files=(os.listdir(folderpath))
        #For the progressbar
        win = ProgressWin(self, len(files))
        #Get the tag of each file and add it to a list
        for file in files:
            if win.wasCanceled(): break
            if tag.link(path.join(folderpath,file)) is None:
                tag.gettags()
                tags.append(tag.tags.copy())
                win.updateVal()                
        self.tablemodel.load(tags, append = appendtags)
        self.table.resizeRowsToContents()
        win.close()
        #print time.strftime("%H : %M : %S")
        
    def savecombos(self):
        
        combos = self.combogroup.combos
        for row in self.table.selectedRows:
            tags={}
            for tag in combos:
                try:
                    curtext=unicode(combos[tag].currentText())
                    if curtext=="<blank>": tags[tag]=""
                    elif curtext=="<keep>": pass
                    else:
                        tags[tag]=unicode(combos[tag].currentText())
                except KeyError:
                    pass
            self.tablemodel.setRowData(row,tags.copy())
            self.tablemodel.writeTag(row,tags.copy())

        
    


class MainWin(QtGui.QMainWindow):
    
    
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        
        def initdir(filename):
            return path.join(sys.path[0],filename)
        
        self.setWindowTitle("Freetag")
        self.cenwid=TableWindow()
        self.setCentralWidget(self.cenwid)
        
        
        
        self.opendir =  QtGui.QAction(QtGui.QIcon(initdir('open.png')), 'Open Folder', self)
        self.opendir.setShortcut('Ctrl+O')
        self.connect(self.opendir, QtCore.SIGNAL('triggered()'), self.openfolder)
        
        self.adddir = QtGui.QAction(QtGui.QIcon(initdir('fileimport.png')), 'Add Folder', self)
        self.connect(self.adddir, QtCore.SIGNAL('triggered()'), self.addfolder)
        
        
        self.savecombotag = QtGui.QAction(QtGui.QIcon(initdir('save.png')), 'Save', self)
        self.savecombotag.setShortcut('Ctrl+S')
        self.connect(self.savecombotag,QtCore.SIGNAL("triggered()"), 
                            self.cenwid.savecombos)

        self.tagfromfile = QtGui.QAction(QtGui.QIcon(initdir('filetotag.png')), 
                                    'Tag from file', self)
        self.connect(self.tagfromfile, QtCore.SIGNAL("triggered()"), 
                                    self.gettagfromfile)

        self.tagtofile = QtGui.QAction(QtGui.QIcon(initdir('tagtofile.png')), 
                                    'Tag to File', self)
        self.connect(self.tagtofile,QtCore.SIGNAL("triggered()"),self.savetagtofile)
        
        self.format = QtGui.QAction(QtGui.QIcon(initdir('cap.png')), 'Title Format', self)
        self.connect(self.format,QtCore.SIGNAL("triggered()"),self.titlecase)

        self.changetracks = QtGui.QAction(QtGui.QIcon(initdir('track.png')), 'Autonumbering Wizard', self)
        self.connect(self.changetracks, QtCore.SIGNAL('triggered()'), self.tracks)
        
        self.renamedir = QtGui.QAction(QtGui.QIcon(initdir("rename.png")), "Rename Dir",self)
        self.connect(self.renamedir, QtCore.SIGNAL("triggered()"), self.renamefolder)
        
        self.importfile = QtGui.QAction(QtGui.QIcon(initdir("import.png")), "Import tags from file",self)
        self.connect(self.importfile, QtCore.SIGNAL("triggered()"), self.FileImport)
        
        menubar = self.menuBar()
        file = menubar.addMenu('&File')
        file.addAction(self.opendir)
        file.addAction(self.savecombotag)
        
        
        self.patterncombo = QtGui.QComboBox()        
        self.patterncombo.addItems(["%artist% - %title%", 
                                    "%artist% - $num(%track%,2) - %title%"])
        self.patterncombo.setEditable(True)
        self.patterncombo.setToolTip("Enter pattern that you want here.")
        self.patterncombo.setStatusTip(self.patterncombo.toolTip())
        self.patterncombo.setFocusPolicy(QtCore.Qt.NoFocus)
        self.patterncombo.setMinimumWidth(500)
        self.connect(self.patterncombo,QtCore.SIGNAL("editTextChanged(QString)"),self.patternchange)
        
        self.toolbar = self.addToolBar("My Toolbar")
        self.toolbar.addAction(self.opendir)
        self.toolbar.addAction(self.savecombotag)
        self.toolbar.addWidget(self.patterncombo)
        self.toolbar.addAction(self.tagfromfile)
        self.toolbar.addAction(self.tagtofile)
        self.toolbar.addAction(self.format)
        self.toolbar.addAction(self.changetracks)
        self.toolbar.addAction(self.adddir)
        self.toolbar.addAction(self.renamedir)
        self.toolbar.addAction(self.importfile)
        
        self.statusbar = self.statusBar()
        self.connect(self.cenwid.tree, QtCore.SIGNAL('itemSelectionChanged()'), self.opentree)
        self.connect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'), self.rowEmpty)
        self.connect(self.cenwid.table, QtCore.SIGNAL('removedRow()'), self.rowEmpty)
        self.connect(self.cenwid.tree, QtCore.SIGNAL('addFolder'), self.openfolder)
        self.setWindowState(QtCore.Qt.WindowMaximized)
                    
    def FileImport(self):
        pattern = unicode(self.patterncombo.currentText())
        filedlg = QtGui.QFileDialog()
        filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder','/media/multi/'))
        if filename != "":
            f = open(filename)
            i = 0
            import importfile
            win = importfile.ImportWindow(self, filename)
            win.setModal(True)
            win.show()
            patternitems = [self.patterncombo.itemText(z) for z in range(self.patterncombo.count())]
            win.patterncombo.addItems(patternitems)
            self.connect(win,QtCore.SIGNAL("Newtags"), self.goddamn)
    
    def goddamn(self,mylist):
        i = 0        
        for z in self.cenwid.table.selectedRows:
            try:
                self.cenwid.table.updaterow(z,mylist[i])
            except IndexError:
                break
            i += 1
    
            
                        
    def renamefolder(self, test = False):
        currentdir = path.dirname(self.cenwid.tablemodel.taginfo[self.cenwid.table.selectedRows[0]]["__filename"])
        filename = path.join(path.dirname(currentdir),path.splitext(path.basename(self.savetagtofile(True)))[0])
        if test == True:
            return unicode("Rename: ") + currentdir + unicode(" to: ") + filename
        result = QtGui.QMessageBox.question (None, unicode("Rename Folder?"), 
                    unicode("Are you sure you want to rename \n ") + currentdir + unicode("\n to \n") + filename, 
                    "&Yes", "&No","", 1, 1)
        if result == 0:
            self.disconnect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'), self.patternchange)
            self.disconnect(self.cenwid.tree, QtCore.SIGNAL('itemSelectionChanged()'), self.opentree)
            try:
                idx = self.cenwid.dirmodel.index(currentdir)
                os.rename(currentdir, filename)
                self.cenwid.dirmodel.refresh(self.cenwid.dirmodel.parent(idx))
                idx = self.cenwid.dirmodel.index(filename)
                self.cenwid.tree.setCurrentIndex(idx)
            except OSError:
                QtGui.QMessageBox.information(self, 'Message',
                   unicode( "I couldn't rename\n") + currentdir + unicode(" to \n") +
                    filename + unicode("\nCheck that you have write access."), QtGui.QMessageBox.Ok)
            self.connect(self.cenwid.tree, QtCore.SIGNAL('itemSelectionChanged()'), self.opentree)
            self.connect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'), self.patternchange)
            self.openfolder(filename)
            
    def rowEmpty(self):
        cenwid = self.cenwid
        #An error gets raised if the table's empty.
        #So we disable everything in that case
        try:
            if cenwid.table.selectedRows != []:
                self.savecombotag.setEnabled(True)
                self.adddir.setEnabled(True)
                self.patterncombo.setEnabled(True)
                self.changetracks.setEnabled(True)
                self.tagtofile.setEnabled(True)
                self.tagfromfile.setEnabled(True)
                self.format.setEnabled(True)
                self.renamedir.setEnabled(True)
                self.importfile.setEnabled(True)
                return
        except AttributeError:
                pass
        
        cenwid.combogroup.disableCombos()
        self.savecombotag.setEnabled(False)
        self.adddir.setEnabled(False)
        self.patterncombo.setEnabled(False)
        self.changetracks.setEnabled(False)
        self.tagtofile.setEnabled(False)
        self.tagfromfile.setEnabled(False)
        self.format.setEnabled(False)
        self.renamedir.setEnabled(False)
        self.importfile.setEnabled(False)
        
    def tracks(self):
        """Shows the window for selecting the range that track
            numbers should be filled in"""
        from formatwin import TrackWindow
        
        row = self.cenwid.table.selectedRows[0]
        numtracks = 0
        try:
            mintrack = long(self.cenwid.table.rowtags(row)["track"])
        except KeyError:
            mintrack=1
        except ValueError:
            mintrack = self.cenwid.table.rowtags(row)["track"]
            try:
                mintrack = long(mintrack[:mintrack.find("/")])
                numtracks = len(self.cenwid.table.selectedRows)
            except ValueError:
                mintrack = 1            
        win = TrackWindow(self, mintrack, numtracks)
        win.setModal(True)
        self.connect(win, QtCore.SIGNAL("newtracks"), self.dotracks)
        win.show()

    
    def dotracks(self, indices ):
        """Sets track numbers for all files in the range, fromnum to tonum"""
        fromnum = indices[0]
        win = ProgressWin(self, len(self.cenwid.table.selectedRows))
        if indices[1] != "":
            num = "/" + indices[1]
        else: num = ""
        for row in self.cenwid.table.selectedRows:
            self.cenwid.tablemodel.setRowData(row,{"track": unicode(fromnum) + num})
            self.cenwid.fillcombos()
            fromnum += 1
            win.updateVal()
        win.close()
        
    def patternchange(self):
        #There's an error everytime an item is deleted, we account for that
        try:
            self.tagfromfile.setStatusTip(unicode("Newtag: ") + unicode(self.gettagfromfile(True)))
            self.tagtofile.setStatusTip(unicode("New Filename: ") + self.savetagtofile(True))
            self.renamedir.setStatusTip(self.renamefolder(True))
        except IndexError: pass
        
    def titlecase(self):
        """Sets the selected tag to Title Case"""
        win = ProgressWin(self, len(self.cenwid.table.selectedRows))
        for row in self.cenwid.table.selectedRows:
            tags=self.cenwid.table.rowtags(row)
            for z in self.cenwid.table.selectedColumns:
                tags[self.cenwid.headerdata[z][1]]=tags[self.cenwid.headerdata[z][1]].title()
                win.updateVal()
            self.cenwid.tablemodel.setRowData(row,tags)
        win.close()
        
    
    def gettagfromfile(self,test = False):
        """Get tags from the selected items.
        If test = False then the table in cenwid is updated."""
        model = self.cenwid.tablemodel
        if test == False:
            win = ProgressWin(self, len(self.cenwid.table.selectedRows))            
            startval = 0
        else:
            row = self.cenwid.table.selectedRows[0]
            return findfunc.filenametotag(unicode(self.patterncombo.currentText()),
                path.basename(model.taginfo[row]["__filename"]), True)
                
        for row in self.cenwid.table.selectedRows:            
            filename = model.taginfo[row]["__filename"]
            newtag = findfunc.filenametotag(unicode(self.patterncombo.currentText()),
                path.basename(filename), True)
            try:
                    model.setRowData(row,newtag)
                    self.cenwid.fillcombos()
                    win.updateVal()
            except IOError:
                QtGui.QMessageBox.information(self, 'Message',
                    "Could not write to file \n" + filename
                    + "\nCheck that you have write access.", QtGui.QMessageBox.Ok)
        win.close()
        
    
    def savetagtofile(self,test=False):
        """Renames the selected files as specified
        by patterncombo.
        
        If test = True then the files are not renamed and
        the new filename of the first selected file is
        returned."""
        taginfo = self.cenwid.tablemodel.taginfo
        
        
        if test == False:
            win = ProgressWin(self, len(self.cenwid.table.selectedRows))            
            startval = 0
        else:
            row = self.cenwid.table.selectedRows[0]
            newfilename = (findfunc.tagtofilename(unicode(self.patterncombo.currentText())
                                    ,taginfo[row], True, taginfo[row]["__ext"] ))
            return path.join(path.dirname(taginfo[row]["__filename"]), self.safe_name(newfilename))            
            
        for row in self.cenwid.table.selectedRows:
            filename = taginfo[row]["__filename"]
            tag = taginfo[row]
            newfilename = (findfunc.tagtofilename(unicode(self.patterncombo.currentText())
                                    ,tag, True, tag["__ext"] ))
            newfilename = path.join(path.dirname(filename), self.safe_name(newfilename))
            
            if test == False:
                try:
                    if os.path.exists(newfilename):
                        result = QtGui.QMessageBox.question (self, "Error?", 
                            "The file: " + newfilename + " exists. Should I overwrite it?", 
                            "&Yes", "&No","", 1, 1)
                        if result == 1:
                            break        
                    os.rename(filename,newfilename)
                except OSError:
                    QtGui.QMessageBox.information(self, 'Message',
                        "Could not write to file \n" + filename
                        + "\nCheck that you have write access.", QtGui.QMessageBox.Ok)
                #Update the table to the new filename
                self.cenwid.table.updaterow(row,{"__filename": newfilename, 
                                        "__path": path.basename(newfilename)})
                self.cenwid.fillcombos()
            else:
                return newfilename
            win.updateVal()
        win.close()
        
    def openfolder(self, filename = None, appenddir = False):
        """Opens a folder. If filename != None, then
        the table is filled with the folder."""
        self.disconnect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'), self.patternchange)
        if filename is None: 
            filedlg = QtGui.QFileDialog()
            filedlg.setFileMode(filedlg.DirectoryOnly)
            filename = unicode(filedlg.getExistingDirectory(self,
                'OpenFolder','/media/multi/',QtGui.QFileDialog.ShowDirsOnly))
        
        if not path.isdir(filename): 
            self.connect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'), self.patternchange)
            return
        
        filename = path.realpath(filename)
        
        self.disconnect(self.cenwid.tree, QtCore.SIGNAL('itemSelectionChanged()'), self.opentree)
        pathindex = self.cenwid.dirmodel.index(filename)
        self.cenwid.tree.setCurrentIndex(pathindex)
        self.cenwid.filltable(filename, appenddir)
        self.connect(self.cenwid.tree, QtCore.SIGNAL('itemSelectionChanged()'), self.opentree)
        self.connect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'), self.patternchange)
        self.setWindowTitle("Freetag: " + filename)
        if appenddir == False:
            self.cenwid.table.selectRow(0)    
        
    def opentree(self):
        filename=unicode(self.cenwid.dirmodel.filePath(self.cenwid.tree.selectedIndexes()[0]))
        self.openfolder(filename)
        
    def addfolder(self):
        self.openfolder(appenddir = True)
    
    def safe_name(self, name):
        """Make a filename safe for use (remove some special chars)"""
        escaped = ""
        for ch in name:
            if ch not in r'/\*?;|': escaped = escaped + ch
        if not escaped: return '""'
        return escaped
        
app = QtGui.QApplication(sys.argv)
filename=sys.argv[-1]
    
qb = MainWin()
qb.show()
qb.rowEmpty()

if path.isdir(filename)==True:
    qb.openfolder(filename)

app.exec_()