from PyQt4.QtGui import *
from PyQt4.QtCore import *
from copy import deepcopy
import os, shutil
from puddlestuff.puddleobjects import PuddleConfig

class DirView(QTreeView):
    """The treeview used to select a directory."""

    def __init__(self, parent = None, subfolders = False, status=None):
        QTreeView.__init__(self,parent)
        self.receives = [('dirschanged', self.selectDirs),
                         ('dirsmoved', self.dirMoved)]
        self.emits = ['loadFiles', 'removeFolders']
        dirmodel = QDirModel()
        dirmodel.setSorting(QDir.IgnoreCase)
        dirmodel.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
        dirmodel.setReadOnly(False)
        dirmodel.setLazyChildCount(False)

        self.setModel(dirmodel)
        [self.hideColumn(column) for column in range(1,4)]

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

        index = self.model().index(QDir.homePath())
        self.setExpanded(index, True)
        while index.parent().isValid():
            index = index.parent()
            self.setExpanded(index, True)
        self.resizeColumnToContents(0)
        self._select = True

    def loadSettings(self):
        t = PuddleConfig()
        settings = QSettings(t.filename, QSettings.IniFormat)
        d = settings.value('main/lastfolder',
                                        QVariant(QDir.homePath())).toString()
        index = self.model().index(d)
        while index.isValid():
            self.expand(index)
            index = index.parent()

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

    def dirMoved(self, olddir, newdir):
        l = self._load
        self._load = False
        model = self.model()
        selectindex = self.selectionModel().select
        getindex = model.index
        idx = getindex(olddir)
        model.refresh(model.parent(idx))
        selectindex(getindex(newdir), QItemSelectionModel.Select)
        self._load = l

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
        if not self._select:
            self._select = True
            return
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
        self._select = False

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

control = ('Filesystem', DirView)
