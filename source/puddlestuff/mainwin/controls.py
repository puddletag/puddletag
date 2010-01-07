from PyQt4.QtGui import *
from PyQt4.QtCore import QDir, QPoint, Qt, QSize, SIGNAL, QMimeData, QUrl
from puddlestuff.puddleobjects import PuddleThread, HeaderSetting, partial, natcasecmp, PicWidget, unique
from puddlestuff.puddlesettings import ColumnSettings
import puddlestuff.audioinfo as audioinfo
from puddlestuff.audioinfo.util import commonimages
from puddlestuff.tagmodel import TagTable
from copy import deepcopy
import os, shutil

class FileTags(QScrollArea):
    def __init__(self, parent=None):
        QScrollArea.__init__(self,parent)
        self._labels = []
        self.grid = QGridLayout()
        self.grid.setSizeConstraint(self.grid.SetFixedSize)
        self.grid.setColumnStretch(1,1)
        self.group = QGroupBox()
        self.group.setLayout(self.grid)
        self.setWidget(self.group)

    def load(self, audio):
        if not self.isVisible():
            self._filename = audio['__filename']
            return
        def what():
            try:
                tags = audioinfo.Tag(audio['__filename'])
            except (OSError, IOError), e:
                tags = {'Error': [e.strerror]}
            return tags
        if hasattr(self, '_t'):
            while self._t.isRunning():
                pass
        self._t = PuddleThread(what)
        self._t.connect(self._t, SIGNAL('threadfinished'), self._load)
        self._t.start()

    def _load(self, audio):
        interaction = Qt.TextSelectableByMouse or Qt.TextSelectableByKeyboard
        if audio:
            try:
                tags = audio.usertags
            except AttributeError:
                tags = audio
        if tags:
            [(z.setVisible(True), v.setVisible(True)) for z, v
                                            in self._labels if not z.isVisible()
                                            or not v.isVisible()]
        else:
            [(z.setVisible(False), v.setVisible(False)) for z, v
                                            in self._labels]
            return
        self.grid.setRowStretch(self.grid.rowCount() - 1, 0)
        if len(tags) > len(self._labels):
            self._labels += [[QLabel(), QLabel()] for z in range(len(tags) - len(self._labels) + 1)]
            row = self.grid.rowCount()
            for d, p in self._labels:
                d.setTextInteractionFlags(interaction)
                p.setTextInteractionFlags(interaction)
                self.grid.addWidget(d, row,0)
                self.grid.addWidget(p, row,1)
                row += 1

        elif len(tags) < len(self._labels):
            [(z.setVisible(False), v.setVisible(False)) for z, v
                                            in self._labels[len(tags):]]

        for key, label in zip(sorted(tags, cmp = natcasecmp), self._labels):
            label[0].setText(key + ':')
            label[1].setText(u'<b>%s</b>' % tags[key][0])
        self.grid.setRowStretch(self.grid.rowCount(), 1)

class FrameCombo(QGroupBox):
    """A group box with combos that allow to edit
    tags individually if so inclined.

    tags should be a list with the tags
    that each combo box should hold specified
    in the form [(Display Value, internal tag)]
    .e.g [("Artist","artist"), ("Track Number", "track")]

    Individual comboboxes can be accessed by using FrameCombo.combos
    which is a dictionary key = tag, value = respective combobox.
    """

    def __init__(self,tags = None,parent= None):
        QGroupBox.__init__(self,parent)
        self.combos = {}
        self.tags = tags
        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)
        if tags is not None:
            self.setCombos(tags)

    def disableCombos(self):
        for z in self.combos:
            if z  == "__image":
                self.combos[z].setImages(None)
            else:
                self.combos[z].clear()
            self.combos[z].setEnabled(False)

    def fillCombos(self, audios):
        combos = self.combos
        for z in combos:
            if z  == "__image":
                combos[z].setImages(None)
            else:
                combos[z].clear()
            combos[z].setEnabled(False)

        self.initCombos()

        tags = dict([(tag,[]) for tag in combos if tag != '__image'])
        images = []
        imagetags = set()
        for audio in audios:
            try:
                imagetags = imagetags.union(audio.IMAGETAGS)
            except AttributeError:
                pass
            if ('__image' in combos):
                if audio.IMAGETAGS:
                    images.append(audio['__image'] if audio['__image'] else {})
                else:
                    images.append({})
            for tag in tags:
                try:
                    if isinstance(audio[tag],(unicode, str)):
                        tags[tag].append(audio[tag])
                    else:
                            tags[tag].append("\\\\".join(audio[tag]))
                except KeyError:
                    tags[tag].append("")

        if '__image' in combos:
            combos['__image'].lastfilename = audios[0]['__filename']
            images = commonimages(images)
            if images == 0:
                combos['__image'].setImageTags(imagetags)
                combos['__image'].context = 'Cover Varies'
                combos['__image'].currentImage = 0
            elif images == None:
                combos['__image'].currentImage = 1
            else:
                combos['__image'].setImageTags(imagetags)
                combos['__image'].images.extend(images)
                combos['__image'].currentImage = 2

        for z in tags:
            tags[z] = list(set(tags[z]))
        #Add values to combos
        for tagset in tags:
            [combos[tagset].addItem(unicode(z)) for z in sorted(tags[tagset])
                    if combos.has_key(tagset)]

        for combo in combos.values():
            combo.setEnabled(True)
            #If a combo has more than 3 items it's not more than one artist, so we
            #set it to the defaultvalue.
            try:
                if (combo.count() > 3) or (combo.count() < 2):
                    combo.setCurrentIndex(0)
                else:
                    combo.setCurrentIndex(2)
            except AttributeError:
                pass

        #There are already prefefined genres so I have to check
        #the selected file's one is there.
        if 'genre' in tags and len(tags['genre']) == 1:
            combo = combos['genre']
            index = combo.findText(tags['genre'][0])
            if index > -1:
                combo.setCurrentIndex(index)
            else:
                combo.setEditText(tags['genre'][0])
        else:
            combos['genre'].setCurrentIndex(0)

    def setCombos(self, tags, rows = None):
        """Creates a vertical column of comboboxes.
        tags are tags is usual in the (tag, backgroundvalue) case[should be enumerable].
        rows are a dictionary with each key being a list of the indexes of tags that should
        be one one row.

        E.g Say you wanted to have the artist, album, title, and comments on
        seperate rows. But then you want year, genre and track on one row. With that
        row being before the comments row. You'd do something like...

        >>>tags = [('Artist', 'artist'), ('Title', 'title'), ('Album', 'album'),
        ...        ('Track', 'track'), ("Comments",'comment'), ('Genre', 'genre'), (u'Year', u'date')]
        >>>rows = {0:[0], 1:[1], 2:[2], 3[3,4,6],4:[5]
        >>>f = FrameCombo()
        >>>f.setCombo(tags,rows)"""
        self.combos = {}
        self.labels = {}

        j = 0
        hbox = [1] * (len(rows) * 2)
        for row in sorted(rows.values()):
            hbox[j] = QHBoxLayout()
            hbox[j + 1] = QHBoxLayout()
            for tag in [tags[z] for z in row]:
                tagval = tag[1]
                self.labels[tagval] = QLabel(tag[0])
                if tagval == '__image':
                    self.labels[tagval].hide()

                    pic = PicWidget()
                    pic.next.setVisible(True)
                    pic.prev.setVisible(True)
                    pic.showbuttons = True
                    pic._image_desc.setEnabled(False)
                    pic._image_type.setEnabled(False)
                    self.combos[tagval] = pic
                else:
                    self.combos[tagval] = QComboBox()
                    self.combos[tagval].setInsertPolicy(QComboBox.NoInsert)
                self.labels[tagval].setBuddy(self.combos[tagval])
                hbox[j].addWidget(self.labels[tagval])
                hbox[j + 1].addWidget(self.combos[tagval])
            self.vbox.addLayout(hbox[j])
            self.vbox.addLayout(hbox[j + 1])
            j+=2

        self.vbox.addStrut(0)
        self.setMaximumHeight(self.sizeHint().height())

    def initCombos(self):
        """Clears the comboboxes and adds two items, <keep> and <blank>.
        If <keep> is selected and the tags in the combos are saved,
        then they remain unchanged. If <blank> is selected, then the tag is removed"""
        for combo in self.combos:
            if combo  == "__image":
                pics = self.combos[combo].loadPics(':/keep.png', ':/blank.png')
                self.combos[combo].setImages(pics)
                self.combos[combo].readonly = [0,1]
            else:
                self.combos[combo].clear()
                self.combos[combo].setEditable(True)
                self.combos[combo].addItems(["<keep>", "<blank>"])
                self.combos[combo].setEnabled(False)

        if 'genre' in self.combos:
            from mutagen.id3 import TCON
            self.combos['genre'].addItems(audioinfo.GENRES)

    def reloadCombos(self, tags):
        self.setCombos(tags)


class DirView(QTreeView):
    """The treeview used to select a directory."""
    def __init__(self, parent = None, subfolders = False):
        QTreeView.__init__(self,parent)
        self.header().setStretchLastSection(False)
        self.header().hide()
        self.subfolders = subfolders
        self.setSelectionMode(self.ExtendedSelection)
        self._lastselection = 0 #If > 0 appends files. See selectionChanged
        self._load = True #If True a loadFiles signal is emitted when
                          #an index is clicked. See selectionChanged.
        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self._dropaction = Qt.MoveAction

    def _copy(self, files):
        """Copies the list in files[0] to the dirname in files[1]."""
        #I have to do it like in the docstring, because the partial function
        #used in contextMenuEvent doesn't support more than one parameter
        #for python < 2.5
        
        dest = files[1]
        files = files[0]
        showmessage = True
        for f in files:
            try:
                if os.path.isdir(f):
                    if f.endswith(u'/'): #Paths ending in '/' have no basename.
                        f = f[:-1]
                    shutil.copytree(f, os.path.join(dest, os.path.basename(f)))
                else:
                    shutil.copy2(f, os.path.join(dest, os.path.basename(f)))
                index = self.model().index(dest)
                self.model().refresh(self.model().parent(index))
            except (IOError, OSError), e:
                if showmessage:
                    text = u"I couldn't copy <b>%s</b> to <b>%s</b> (%s)" % (f,
                                                            dest, e.strerror)
                    ret = self.warningMessage(text, len(files))
                    if ret is True:
                        showmessage = False
                    elif ret is False:
                        break

    def _createFolder(self, index):
        """Prompts the user to create a child for in index."""
        model = self.model()
        text, ok = QInputDialog.getText(self.parentWidget(),'puddletag', 'Enter'
                    ' a name for the directory', QLineEdit.Normal, 'New Folder')
        dirname = unicode(self.model().filePath(index))
        text = os.path.join(dirname, unicode(text))
        if ok:
            try:
                os.mkdir(text)
                self.model().refresh(index)
                self.expand(index)
            except (OSError, IOError), e:
                text = u"I couldn't create <b>%s</b> (%s)" % (text, e.strerror)
                self.warningMessage(text, 1)

    def _deleteFolder(self, index):
        """Deletes the folder at index."""
        model = self.model()
        getfilename = model.filePath
        filename = unicode(getfilename(index))
        ret = QMessageBox.information(self.parentWidget(), 'Delete?', u'Do you '
                u" want to remove the folder <b>%s</b> and all it's contents?" %
                filename, QMessageBox.Yes, QMessageBox.No)
        if ret == QMessageBox.Yes:
            try:
                shutil.rmtree(filename)
            except (OSError, IOError), e:
                text = u"I couldn't delete <b>%s</b> (%s)" % (filename, e.strerror)
                self.warningMessage(text, 1)
                return 
            model.refresh(index.parent())
            valid = self.selectedFilenames
            if filename in valid:
                valid.remove(filename)
                self.emit(SIGNAL('removeFolders'), valid)

    def _move(self, files):
        """Moves the list in files[0] to the dirname in files[1]."""
        #I have to do it like in the docstring, because the partial function
        #used in contextMenuEvent doesn't support more than one parameter
        #for python < 2.5
        showmessage = True
        dest = files[1]
        files = files[0]
        valid = self.selectedFilenames

        model = self.model()
        refresh = model.refresh
        parent = model.parent
        getindex = model.index
        self._load = False
        newdirnames = []
        for f in files:
            try:
                if f.endswith(u'/'):
                    f = f[:-1]
                newdir = os.path.join(dest, os.path.basename(f))
                if newdir == f:
                    continue
                shutil.move(f, newdir)
                newdirnames.append(newdir)
                if f in valid:
                    self.emit(SIGNAL('changeFolder'), f, newdir)
            except (IOError, OSError), e:
                if showmessage:
                    text = u"I couldn't move <b>%s</b> to <b>%s</b> (%s)" % (f,
                                                            dest, e.strerror)
                    ret = self.warningMessage(text, len(files))
                    if ret is True:
                        showmessage = False
                    elif ret is False:
                        break
        refresh(parent(getindex(dest)))
        self.expand(getindex(dest))
        select = self.selectionModel().select
        for d in newdirnames:
            index = getindex(d)
            self.expand(index)
            selection = QItemSelection(index, index)
            select(selection, QItemSelectionModel.Select)
        self._load = True

    def _renameFolder(self, index):
        """Prompts the user to rename the folder at index."""
        model = self.model()
        filename = unicode(model.filePath(index))
        dirname = os.path.dirname(filename)
        text, ok = QInputDialog.getText(self.parentWidget(),'puddletag',
                        u'Enter a new name for the directory',
                        QLineEdit.Normal, os.path.basename(filename))
        if ok:
            newfilename = os.path.join(dirname, unicode(text))
            try:
                os.rename(filename, newfilename)
            except (IOError, OSError), e:
                text = u"I couldn't rename <b>%s</b> to <b>%s</b> (%s)" % \
                                (filename, newfilename, e.strerror)
                self.warningMessage(text, 1)
                return
            model.refresh(index.parent())
            temp = bool(self._load)
            self._load = False
            index = model.index(newfilename)
            self.selectionModel().select(index, QItemSelectionModel.Select)
            if filename in self.selectedFilenames:
                self.emit(SIGNAL('changeFolder'), filename, newfilename)
            self._load = temp

    def _setCurrentIndex(self):
        if self._append:
            self.selectionModel().select(self.t.retval, QItemSelectionModel.Select)
        else:
            self.setCurrentIndex(self.t.retval)
        self.resizeColumnToContents(0)
        self.setEnabled(True)
        self.blockSignals(False)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        create = QAction('Create Folder', self)
        rename = QAction('Rename Folder', self)
        delete = QAction(QIcon(":/remove.png"), 'Delete Folder', self)
        refresh = QAction("Refresh", self)
        sep = QAction(self)
        sep.setSeparator(True)
        index = self.indexAt(event.pos())

        self.connect(refresh, SIGNAL('triggered()'), partial(self.model().refresh, index))
        self.connect(delete, SIGNAL('triggered()'), partial(self._deleteFolder, index))
        self.connect(create, SIGNAL('triggered()'), partial(self._createFolder, index))
        self.connect(rename, SIGNAL('triggered()'), partial(self._renameFolder, index))
        [menu.addAction(z) for z in [create, rename, refresh, sep, delete]]
        menu.exec_(event.globalPos())

    def _getDefaultDrop(self):
        return self._dropaction
    
    def _setDefaultDrop(self, action):
        if action in [Qt.MoveAction, Qt.CopyAction]:
            self._dropaction = action
        else:
            self._dropaction = None

    def clearSelection(self, *args):
        self.blockSignals(True)
        self.selectionModel().clearSelection()
        self.blockSignals(False)
        self.emit(SIGNAL('removeFolders'), [], True)

    defaultDropAction = property(_getDefaultDrop, _setDefaultDrop)
        
    def dropEvent(self, event):
        """Shows a menu to copy or move when files dropped."""
        files = [unicode(z.path()) for z in event.mimeData().urls()]
        while '' in files:
            files.remove('')
        dest = unicode(self.model().filePath(self.indexAt(event.pos())))

        if not self.defaultDropAction:
            menu = QMenu(self)
            move = QAction('Move', self)
            copy = QAction('Copy', self)
            sep = QAction(self)
            sep.setSeparator(True)
            cancel = QAction('Cancel', self)
            self.connect(move, SIGNAL('triggered()'), partial(self._move, [files, dest]))
            self.connect(copy, SIGNAL('triggered()'), partial(self._copy, [files, dest]))
            [menu.addAction(z) for z in [move, copy, sep, cancel]]
            action = menu.exec_(self.mapToGlobal (event.pos()))
            if action == copy:
                event.setDropAction(Qt.CopyAction)
            elif action == move:
                event.setDropAction(Qt.MoveAction)
            #else:
                #event.setDropAction(Qt.IgnoreAction)
            event.accept()
        else:
            temp = {Qt.CopyAction: self._copy, Qt.MoveAction:self._move}
            #event.setDropAction(self.defaultDropAction)
            temp[self.defaultDropAction]([files, dest])
            event.accept()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
        QTreeView.dragEnterEvent(self, event)
        
    def expand(self, index):
        self.resizeColumnToContents(0)
        QTreeView.expand(self, index)

    #def mouseMoveEvent(self, event):
        #if self.StartPosition is None:
            #QTreeView.mouseMoveEvent(self, event)
            #return
        #pnt = QPoint(*self.StartPosition)
        #if (event.pos() - pnt).manhattanLength() < QApplication.startDragDistance():
            #return
        #drag = QDrag(self)
        #mimedata = QMimeData()
        #mimedata.setUrls([QUrl(f) for f in self.selectedFilenames])
        #drag.setMimeData(mimedata)
        #drag.setHotSpot(event.pos() - self.rect().topLeft())
        #if self.defaultDropAction:
            #cursor = self.defaultDropAction
        #else:
            #cursor = Qt.MoveAction
        #drag.setDragCursor (QPixmap(), cursor)
        #dropaction = drag.exec_(cursor)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.RightButton:
            self.StartPosition = None
            self.contextMenuEvent(event)
            return
        #if event.buttons() == Qt.LeftButton:
            #self.StartPosition = [event.pos().x(), event.pos().y()]
        QTreeView.mousePressEvent(self, event)
        self.resizeColumnToContents(0)

    def selectIndex(self, index):
        self.selectionModel().select(QItemSelection(index, index),
                                            QItemSelectionModel.Select)

    def _selectedFilenames(self):
        filename = self.model().filePath
        return list(set([unicode(filename(i)) for i in self.selectedIndexes()]))
    
    selectedFilenames = property(_selectedFilenames)

    def setFileIndex(self, filename, append = False):
        """Use instead of setCurrentIndex for threaded index changing."""
        self.blockSignals(True)
        self.t = PuddleThread(lambda: self.model().index(filename))
        self.connect(self.t, SIGNAL('finished()'), self._setCurrentIndex)
        self.setEnabled(False)
        self.t.start()
        self._append = append

    def selectDirs(self, dirlist):
        self.blockSignals(True)
        load = self._load
        self._load = False
        self.selectionModel().clear()
        selectindex = self.selectionModel().select
        getindex = self.model().index
        parent = self.model().parent
        
        for d in dirlist:
            index = getindex(d)
            selectindex(index, QItemSelectionModel.Select)
            i = parent(index)
            parents = []
            while i.isValid():
                parents.append(i)
                i = parent(i)
            [self.expand(p) for p in parents]
        self.resizeColumnToContents(0)
        self._load = load
        self.blockSignals(False)

    def selectionChanged(self, selected, deselected):
        QTreeView.selectionChanged(self, selected, deselected)
        if not self._load:
            self._lastselection = len(self.selectedIndexes())
            return
        self.resizeColumnToContents(0)
        getfilename = self.model().filePath
        dirs = list(set([unicode(getfilename(i)) for i in selected.indexes()]))
        old = list(set([unicode(getfilename(i)) for i in deselected.indexes()]))
        if self._lastselection:
            if len(old) == self._lastselection:
                append = False
            else:
                append = True
        else:
            append = False
        dirs = list(set(dirs).difference(old))
        if old:
            self.emit(SIGNAL('removeFolders'), old, False)
        if dirs:
            self.emit(SIGNAL('loadFiles'), None, dirs, append)
        self._lastselection = len(self.selectedIndexes())

    def warningMessage(self, text, numfiles):
        """Just shows a warning box with text (in HTML). Should only be called
        when errors occured.

        single is the number of files that are being written. If it is 1, then
        just a warningMessage is shown.

        Returns:
            True if yes to all.
            False if No.
            None if just yes."""
        if numfiles > 1:
            text = text + u'<br />Do you want to continue?'
            msgargs = (QMessageBox.Warning, QMessageBox.Yes or QMessageBox.Default,
                        QMessageBox.No or QMessageBox.Escape, QMessageBox.YesAll)
            mb = QMessageBox('Error', text , *(msgargs + (self.parentWidget(),)))
            ret = mb.exec_()
            if ret == QMessageBox.No:
                return False
            elif ret == QMessageBox.YesAll:
                return True
        else:
            QMessageBox.warning(self.parentWidget(), 'puddletag Error', text)

class TableHeader(QHeaderView):
    """A headerview put here simply to enable the contextMenuEvent
    so that I can show the edit columns menu.

    Call it with tags in the usual form, to set the top header."""
    def __init__(self, orientation, tags = None, parent = None):
        QHeaderView.__init__(self, orientation, parent)
        if tags is not None: self.tags = tags
        self.setClickable(True)
        self.setHighlightSections(True)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        settings = menu.addAction("&Select Columns")
        self.connect(settings, SIGNAL('triggered()'), self.setTitles)
        menu.exec_(event.globalPos())

    def mousePressEvent(self,event):
        if event.button == Qt.RightButton:
            self.contextMenuEvent(event)
            return
        self.emit(SIGNAL('saveSelection'))
        QHeaderView.mousePressEvent(self, event)

    def setTitles(self):
        self.win = ColumnSettings(showok = True)
        self.win.setModal(True)
        self.win.show()
        self.connect(self.win, SIGNAL("headerChanged"), self.headerChanged)

    def headerChanged(self, val):
        self.emit(SIGNAL("headerChanged"), val)


class TableWindow(QSplitter):
    """It's called a TableWindow just because
    the main widget is a table even though it uses a splitter.

    The table allows the editing of tags and stuff like that.

    Important methods are:
    inittable -> Creates table, gets defaults values and shit
    fillTable -> Fills the table with tags from the folder specified.
    setNewHeader -> Sets the header of the table to what you want.
                    tags are specified in the usual way"""

    def __init__(self, parent=None):
        QSplitter.__init__(self, parent)


    def inittable(self, headerdata = None):
        """This is here, because I want to be able to initialize
        many of the tables values from other functions
        (like when the app starts and settings are being restored).

        Call it with headerdata(as usual) to set the titles."""
        if not headerdata:
            headerdata = [('',''), ('','')]
        self.table = TagTable(headerdata, self)
        self.headerdata = headerdata
        header = TableHeader(Qt.Horizontal, self.headerdata, self)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(0, Qt.AscendingOrder)
        self.table.setHorizontalHeader(header)
        self.tablemodel = self.table.model()

        grid = QGridLayout()
        grid.addWidget(self.table)
        self.setLayout(grid)

        self.connect(self.table.horizontalHeader(), SIGNAL("sectionClicked(int)"),
             self.sortTable)
        self.connect(header, SIGNAL("headerChanged"), self.setNewHeader)

    def setNewHeader(self, tags):
        """Used for 'hotswapping' of the table header.

        If you want to set the table header while the app
        is running, then this is the methods you should use.

        tags are a list of tags defined as usual(See FrameCombo's docstring).

        Nothing is returned, if the function is successful, then you should
        see the correct results."""
        try:
            sortedtag = self.headerdata[self.sortColumn][::]
        except IndexError:
            sortedtag = tags[0][::]
        model = self.table.model()

        if len(self.headerdata) < len(tags):
            model.insertColumns(len(self.headerdata) - 1, len(tags) - 1)

        columnwidths = [[tag, self.table.columnWidth(index)] for index, tag in enumerate(self.headerdata)]

        if len(self.headerdata) > len(tags):
            #I'm removing one column at a time, because removing many at a time, doesn't
            #seem work well all the time(I think this is a problem early versions of PyQt).
            #This works(All the time, I think).
            [model.removeColumn(0) for z in xrange(len(tags), len(self.headerdata))]

        [model.setHeaderData(i, Qt.Horizontal, v, Qt.DisplayRole) for i,v in enumerate(tags)]

        for z in columnwidths:
            if z[0] in self.headerdata:
                self.table.setColumnWidth(self.headerdata.index(z[0]), z[1])

        #self.headerdata = model.headerdata
        self.table.horizontalHeader().tags = self.headerdata

        if sortedtag in self.headerdata:
            self.sortTable(self.headerdata.index(sortedtag))
        else:
            self.sortTable(self.sortColumn)

    def sortTable(self,column):
        self.sortColumn = column
        self.table.sortByColumn(column)
        self.setFocus()

    def fillTable(self,folderpath, appendtags = False):
        """See TagTable's fillTable method for more details."""
        self.table.fillTable(folderpath, appendtags)
        if not appendtags:
            self.sortTable(self.sortColumn)

    def setGridVisible(self, val):
        if (val is True) or (val > 0):
            self.table.setGridStyle(Qt.SolidLine)
        else:
            self.table.setGridStyle(Qt.NoPen)

    def getGridVisible(self):
        if self.table.gridStyle() > 0:
            return True
        else:
            return False

    gridvisible = property(getGridVisible, setGridVisible)
