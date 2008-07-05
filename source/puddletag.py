from PyQt4 import QtGui, QtCore
import sys, audioinfo,os, copy, pdb
import abstract, findfunc, formatwin
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
        
    def initCombos(self):
        """Clears the comboboxes and adds two items, <keep> and <blank>.
        If <keep> is selected and the tags in the combos are saved, 
        then they remain unchanged. If <blank> is selected, then the tag is removed"""
        for combo in self.combos:
            self.combos[combo].clear()
            self.combos[combo].setEditable(True)
            self.combos[combo].addItems(["<keep>", "<blank>"])
            self.combos[combo].setEnabled(False)
        


class DirView(QtGui.QTreeView):
    """The treeview used to select a directory."""
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
    
    def mousePressEvent(self,event):
        if event.button == QtCore.Qt.RightButton:
            self.contextMenuEvent(event)
            return
        QtGui.QTreeView.mousePressEvent(self, event)

    def what(self):
        self.emit(QtCore.SIGNAL("addFolder", self.model().filePath(self.selectedIndexes()[0])))


class TableWindow(QtGui.QWidget):
    """It's called a TableWindow just because
    the main widget is a table.
    
    The table allows the editing of tags
    and stuff like that. Important methods are:
    
    fillTable -> Fills the table with tags from the folder specified.
    fillCombos -> Fills the comboboxes with the tags of the selected files.
    saveCombos -> Saves the values in the comboboxes."""
    
    def __init__(self,parent=None):
        QtGui.QWidget.__init__(self,parent)
        self.resize(1000,800)
        
        self.table = abstract.TableShit(self)
        self.headerdata = ([("Path", "__path"), ("Artist", "artist"), 
                            ("Title", "title"), ("Album", "album"), \
                            ("Track", "track"), ("Length","__length")])
        self.tablemodel = abstract.TagModel(self.headerdata)
        delegate = abstract.DelegateShit(self)
        self.table.setItemDelegate(delegate)
        self.table.setModel(self.tablemodel)
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        
        grid = QtGui.QGridLayout()
        grid.addWidget(self.table,0,1,2,1)
        self.setLayout(grid)
        
        self.connect(header, QtCore.SIGNAL("sectionClicked(int)"),
             self.sortTable)
        
        #Need's some cleaning
        i = 0
        for z in [238, 202, 243, 203, 54]:
            self.table.setColumnWidth(i, z)
            i += 1
        
    def sortTable(self,val):
        self.table.sortByColumn(val)
        #This is due to the odd behaviour of the table
        self.setFocus()
                        
        #print time.strftime("%H : %M : %S")
        
    def fillTable(self,folderpath, appendtags = False):
        """Fills self.table with the tags as retrieved from the
        directory folderpath.
        If appendtags = True, the new folder is just appended."""
        
        #import time
        #print folderpath
        #print time.strftime("%H : %M : %S")
        tag = audioinfo.Tag()
        tags = []
        files = (os.listdir(folderpath))
        #For the progressbar
        win = ProgressWin(self, len(files))
        #Get the tag of each file and add it to a list
        for file in files:
            if win.wasCanceled(): break
            if tag.link(path.join(folderpath, file)) is None:
                tag.gettags()
                tags.append(tag.tags.copy())
                win.updateVal()                
        self.tablemodel.load(tags, append = appendtags)
        self.table.resizeRowsToContents()
        win.close()
        #print time.strftime("%H : %M : %S")
        

class MainWin(QtGui.QMainWindow):        
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        
        initdir = lambda filename: os.path.join(sys.path[0], filename)
        
        self.setWindowTitle("Freetag")
        self.cenwid = TableWindow()
        #self.setCentralWidget(self.cenwid)
        
        self.dirmodel = QtGui.QDirModel()
        self.dirmodel.setSorting(QtCore.QDir.IgnoreCase)
        self.dirmodel.setFilter(QtCore.QDir.AllDirs)
        self.dirmodel.setReadOnly(False)
        
        self.tree = DirView()
        self.tree.setModel(self.dirmodel)
        #self.tree.setMaximumWidth(300)
        self.tree.setMinimumSize(300,300)
        [self.tree.hideColumn(column) for column in range(1,4)]
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        
        #Action for opening a folder
        self.opendir =  QtGui.QAction(QtGui.QIcon(initdir('open.png')), 'Open Folder', self)
        self.opendir.setShortcut('Ctrl+O')
        self.connect(self.opendir, QtCore.SIGNAL('triggered()'), self.openFolder)
        
        #Action for adding another folder
        self.adddir = QtGui.QAction(QtGui.QIcon(initdir('fileimport.png')), 'Add Folder', self)
        self.connect(self.adddir, QtCore.SIGNAL('triggered()'), self.addFolder)
        
        #Action for saving tags in combos
        self.savecombotag = QtGui.QAction(QtGui.QIcon(initdir('save.png')), 'Save Tags', self)
        self.savecombotag.setShortcut('Ctrl+S')
        self.connect(self.savecombotag,QtCore.SIGNAL("triggered()"), 
                            self.saveCombos)
        
        #Action for importing tags from files
        self.tagfromfile = QtGui.QAction(QtGui.QIcon(initdir('filetotag.png')), 
                                    'Tag from file', self)
        self.connect(self.tagfromfile, QtCore.SIGNAL("triggered()"), 
                                    self.getTagFromFile)

        self.tagtofile = QtGui.QAction(QtGui.QIcon(initdir('tagtofile.png')), 
                                    'Tag to File', self)
        self.connect(self.tagtofile,QtCore.SIGNAL("triggered()"),self.saveTagToFile)
        
        #I'm using the name format because this will be expanded on quite a bit
        self.format = QtGui.QAction(QtGui.QIcon(initdir('cap.png')), 'Title Format', self)
        self.connect(self.format,QtCore.SIGNAL("triggered()"),self.titleCase)
        
        #Autonumbering shit
        self.changetracks = QtGui.QAction(QtGui.QIcon(initdir('track.png')), 'Autonumbering Wizard', self)
        self.connect(self.changetracks, QtCore.SIGNAL('triggered()'), self.tracks)
        
        
        self.renamedir = QtGui.QAction(QtGui.QIcon(initdir("rename.png")), "Rename Dir",self)
        self.connect(self.renamedir, QtCore.SIGNAL("triggered()"), self.renameFolder)
        
        self.importfile = QtGui.QAction(QtGui.QIcon(initdir("import.png")), "Import tags from file",self)
        self.connect(self.importfile, QtCore.SIGNAL("triggered()"), self.fileImport)
        
        menubar = self.menuBar()
        file = menubar.addMenu('&File')
        file.addAction(self.opendir)
        file.addAction(self.savecombotag)
        
        
        self.patterncombo = QtGui.QComboBox()
        self.patterncombo.setEditable(True)
        self.patterncombo.setToolTip("Enter pattern that you want here.")
        self.patterncombo.setStatusTip(self.patterncombo.toolTip())
        self.patterncombo.setFocusPolicy(QtCore.Qt.NoFocus)
        self.patterncombo.setMinimumWidth(500)
        
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
        self.connect(self.tree, QtCore.SIGNAL('itemSelectionChanged()'), self.openTree)
        self.connect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'), self.rowEmpty)
        self.connect(self.cenwid.table, QtCore.SIGNAL('removedRow()'), self.rowEmpty)
        self.connect(self.tree, QtCore.SIGNAL('addFolder'), self.openFolder)
        self.setWindowState(QtCore.Qt.WindowMaximized)
        
        self.combogroup = FrameCombo(self.cenwid.headerdata[1:-1] + [("Year","date")], self)
        self.combogroup.setMinimumSize(300,300)
        self.connect(self.cenwid.table, QtCore.SIGNAL('itemSelectionChanged()'),
                                         self.fillcombos)
                                         
        self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.hsplitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.hsplitter.addWidget(self.combogroup)
        self.hsplitter.addWidget(self.tree)
        self.splitter.addWidget(self.hsplitter)
        self.splitter.addWidget(self.cenwid)
        self.setCentralWidget(self.splitter)
        self.loadInfo()
        self.connect(self.patterncombo,QtCore.SIGNAL("editTextChanged(QString)"),self.patternChange)
    
    def loadInfo(self):
        settings = QtCore.QSettings()
        columnwidths = settings.value("editor/Column").toStringList()
        i = 0
        for z in columnwidths:            
            self.cenwid.table.setColumnWidth(i,int(z))
            i += 1
        patterns = settings.value("editor/patterns").toStringList()
        self.patterncombo.clear()
        self.patterncombo.addItems(patterns)
        self.splitter.restoreState(settings.value("splittersize").toByteArray())
        self.hsplitter.restoreState(settings.value("hsplittersize").toByteArray())
        print self.splitter.sizes()
        print self.hsplitter.sizes()
    
    def closeEvent(self, event):
        settings = QtCore.QSettings()
        table = self.cenwid.table
        columnwidths = QtCore.QStringList([str(table.columnWidth(z)) for z in range(table.model().columnCount())])
        settings.setValue("editor/Column",QtCore.QVariant(columnwidths))
        patterns = QtCore.QStringList()
        for z in xrange(self.patterncombo.count()):
            patterns.append(self.patterncombo.itemText(z))
        settings.setValue("editor/patterns",QtCore.QVariant(patterns))
        settings.setValue("splittersize", QtCore.QVariant(self.splitter.saveState()))
        settings.setValue("hsplittersize", QtCore.QVariant(self.hsplitter.saveState()))
                            
    def fillcombos(self):
        """Fills the QComboBoxes in FrameCombo with
        the tags selected from self.table. """
        
        #import time
        #print "run"
        #print time.strftime("%H : %M : %S")
        combos = self.combogroup.combos
        self.combogroup.initCombos()        
        mydict = {}
        
        #Removes all duplicate entries for the combos
        #by adding them to a set.
        table = self.cenwid.table
        for row in table.selectedRows:
            taginfo = table.rowTags(row)
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
                        
    def saveCombos(self):
        """Saves the values to the tags in the combos."""
        combos = self.combogroup.combos        
        win = ProgressWin(self, len(self.cenwid.table.selectedRows))
        tablemodel = self.cenwid.tablemodel
        for row in self.cenwid.table.selectedRows:
            if win.wasCanceled(): break
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
            win.updateVal()            
            tablemodel.setRowData(row,tags.copy())
            tablemodel.writeTag(row,tags.copy())
        win.close()                                    
                        
    def fileImport(self):
        """Opens a text file so that tags can be
        imported from it."""
        pattern = unicode(self.patterncombo.currentText())
        filedlg = QtGui.QFileDialog()
        filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder','/media/multi/'))
        if filename != "":
            f = open(filename)
            i = 0
            win = formatwin.ImportWindow(self, filename)
            win.setModal(True)
            win.show()
            patternitems = [self.patterncombo.itemText(z) for z in range(self.patterncombo.count())]
            win.patterncombo.addItems(patternitems)
            self.connect(win,QtCore.SIGNAL("Newtags"), self.setSelectedTags)
            self.fillCombos()
    
    def setSelectedTags(self, taglist):
        """Sets the selected files' tags to the tags
        in taglist."""
        i = 0 
        win = ProgressWin(self, len(self.cenwid.table.selectedRows))
        for z in self.cenwid.table.selectedRows:
            if win.wasCanceled(): break
            try:
                self.cenwid.table.updateRow(z, taglist[i])
            except IndexError:
                break
            i += 1
            win.updateVal()
        win.close()
        self.fillCombos()
                                        
    def renameFolder(self, test = False):
        """This is best explained with an example.
        
        Okay, let's say that you've selected a file and want
        to rename the files directory based on that file.
        This function renames the directory using the
        pattern in self.patterncombo.
        
        If test is True then the new filename is returned
        and nothing else is done."""
        
        selectionChanged = QtCore.SIGNAL('itemSelectionChanged()')
        currentdir = path.dirname(
                        self.cenwid.tablemodel.taginfo 
                            [self.cenwid.table.selectedRows[0]]["__filename"])                            
        filename = path.join(path.dirname(currentdir),
                     path.splitext(path.basename(self.saveTagToFile(True)))[0])
        
        if test == True:
            return unicode("Rename: ") + currentdir + unicode(" to: ") + filename
        
        result = QtGui.QMessageBox.question (None, unicode("Rename Folder?"), 
                    unicode("Are you sure you want to rename \n ") + currentdir + unicode("\n to \n") + filename, 
                    "&Yes", "&No","", 1, 1)
        
        if result == 0:
            #All this disconnecting and reconnecting is to prevent
            #any extraneous loading of folders.
            self.disconnect(self.cenwid.table, selectionChanged, self.patternChange)
            self.disconnect(self.tree, selectionChanged, self.openTree)
            try:
                idx = self.dirmodel.index(currentdir)
                os.rename(currentdir, filename)
                self.dirmodel.refresh(self.dirmodel.parent(idx))
                idx = self.dirmodel.index(filename)
                self.tree.setCurrentIndex(idx)
            except OSError:
                QtGui.QMessageBox.information(self, 'Message',
                   unicode( "I couldn't rename\n") + currentdir + unicode(" to \n") +
                    filename + unicode("\nCheck that you have write access."), QtGui.QMessageBox.Ok)
            self.connect(self.tree, selectionChanged, self.openTree)
            self.connect(self.cenwid.table, selectionChanged, self.patternChange)
            #I'm opening the folder here, because reloading shit just seems
            #complicated
            self.openFolder(filename)
            self.fillCombos()
            
    def rowEmpty(self):
        """If nothing's selected, disable what needs to be disabled."""
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
        
        self.combogroup.disableCombos()
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
        """Shows the autonumbering wizard and sets the tracks
            numbers should be filled in"""        
        
        row = self.cenwid.table.selectedRows[0]
        numtracks = len(self.cenwid.table.selectedRows)
        try:
            mintrack = min([long(self.cenwid.table.rowTags(row)["track"]) \
                                for row in self.cenwid.table.selectedRows])
        except KeyError:
            #No track was specified, just set it to 1
            mintrack = 1
        except ValueError:
            #The tracks are probably in trackno/numtracks format
            mintrack = self.cenwid.table.rowTags(row)["track"]
            try:
                mintrack = long(mintrack[:mintrack.find("/")])
            except ValueError:
                #Tracks are probably text, so we make them numbers
                mintrack = 1
        win = formatwin.TrackWindow(self, mintrack, numtracks)
        win.setModal(True)
        self.connect(win, QtCore.SIGNAL("newtracks"), self.doTracks)
        win.show()

    
    def doTracks(self, indices):
        """Sets the track numbers specified in indices.
        The first item of indices is the starting track.
        The second item of indices is the number of tracks."""
        
        fromnum = indices[0]
        if indices[1] != "":
            num = "/" + indices[1]
        else: num = ""
        rows = self.cenwid.table.selectedRows
        taglist = [{"track": unicode(z) + num} for z in range(1, len(rows) + 1)]
        self.setSelectedTags(taglist)
        
    def patternChange(self):
        """This function is called everytime patterncombo changes.
        It sets the values of the StatusTips for various actions
        to a preview of the resulf if that action is triggered."""
        #There's an error everytime an item is deleted, we account for that
        try:
            self.tagfromfile.setStatusTip(unicode("Newtag: ") + unicode(self.getTagFromFile(True)))
            self.tagtofile.setStatusTip(unicode("New Filename: ") + self.saveTagToFile(True))
            self.renamedir.setStatusTip(self.renameFolder(True))
        except IndexError: pass
        
    def titleCase(self):
        """Sets the selected tag to Title Case"""
        import functions
        win = ProgressWin(self, len(self.cenwid.table.selectedRows))
        for row in self.cenwid.table.selectedRows:
            if win.wasCanceled(): break
            tags = self.cenwid.table.rowTags(row)
            for z in self.cenwid.table.selectedColumns:
                val = self.cenwid.headerdata[z][1] 
                tags[val] = functions.titleCase(tags[val])
                #tags[val] = functions.replaceAsWord(tags[val],"Ft","ft")
                win.updateVal()
            self.cenwid.tablemodel.setRowData(row,tags)
        win.close()
        
    
    def getTagFromFile(self, test = False):
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
            if win.wasCanceled(): break            
            filename = model.taginfo[row]["__filename"]
            newtag = findfunc.filenametotag(unicode(self.patterncombo.currentText()),
                path.basename(filename), True)
            try:
                    model.setRowData(row,newtag)
                    self.fillcombos()
                    win.updateVal()
            except IOError:
                QtGui.QMessageBox.information(self, 'Message',
                    "Could not write to file \n" + filename
                    + "\nCheck that you have write access.", QtGui.QMessageBox.Ok)
        win.close()
        
    
    def saveTagToFile(self,test=False):
        """Renames the selected files as specified
        by patterncombo.
        
        If test = True then the files are not renamed and
        the new filename of the first selected file is
        returned."""
        taginfo = self.cenwid.tablemodel.taginfo
                
        if test == False:
            win = ProgressWin(self, len(self.cenwid.table.selectedRows))
        else:
            #Just return an example value.
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
                self.cenwid.table.updateRow(row,{"__filename": newfilename, 
                                        "__path": path.basename(newfilename)})
                self.fillcombos()
            else:
                return newfilename
            win.updateVal()
        win.close()
        
    def openFolder(self, filename = None, appenddir = False):
        """Opens a folder. If filename != None, then
        the table is filled with the folder."""
        selectionChanged = QtCore.SIGNAL("itemSelectionChanged()")
        self.disconnect(self.cenwid.table, selectionChanged, self.patternChange)
        
        if filename is None: 
            filedlg = QtGui.QFileDialog()
            filedlg.setFileMode(filedlg.DirectoryOnly)
            filename = unicode(filedlg.getExistingDirectory(self,
                'OpenFolder','/media/multi/',QtGui.QFileDialog.ShowDirsOnly))
        
        if not path.isdir(filename): 
            self.connect(self.cenwid.table, selectionChanged, self.patternChange)
            return
        
        #I'm doing this just to be safe.
        filename = path.realpath(filename)
        
        self.disconnect(self.tree, selectionChanged, self.openTree)
        pathindex = self.dirmodel.index(filename)
        self.tree.setCurrentIndex(pathindex)
        self.cenwid.fillTable(filename, appenddir)
        self.connect(self.tree, selectionChanged, self.openTree)
        self.connect(self.cenwid.table, selectionChanged, self.patternChange)
        self.setWindowTitle("Freetag: " + filename)
        if appenddir == False:
            self.cenwid.table.selectRow(0)
        
    def openTree(self):
        filename = unicode(self.dirmodel.filePath(self.tree.selectedIndexes()[0]))
        self.openFolder(filename)
        
    def addFolder(self):
        self.openFolder(appenddir = True)
    
    def safe_name(self, name):
        """Make a filename safe for use (remove some special chars)"""
        escaped = ""
        for ch in name:
            if ch not in r'/\*?;|': escaped = escaped + ch
        if not escaped: return '""'
        return escaped
        
app = QtGui.QApplication(sys.argv)
filename=sys.argv[-1]
app.setOrganizationName("Puddle Inc.")
app.setApplicationName("puddletag")   
    
qb = MainWin()
qb.show()
qb.rowEmpty()

if path.isdir(filename)==True:
    qb.openFolder(filename)

app.exec_()