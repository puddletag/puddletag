from PyQt4.QtGui import *
from PyQt4.QtCore import *
from copy import deepcopy
import os, shutil, pdb, mutex
from puddlestuff.puddleobjects import PuddleConfig, PuddleThread
from puddlestuff.constants import LEFTDOCK
mutex = mutex.mutex()
qmutex = QMutex()

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
        self.header().setResizeMode(QHeaderView.ResizeToContents)

        self.setModel(dirmodel)
        [self.hideColumn(column) for column in range(1,4)]

        self.header().setStretchLastSection(True)
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

    def clearSelection(self, *args):
        self.blockSignals(True)
        self.selectionModel().clearSelection()
        self.blockSignals(False)
        self.emit(SIGNAL('removeFolders'), [], True)

    def dirMoved(self, dirs):
        l = self._load
        self._load = False
        model = self.model()
        selectindex = self.selectionModel().select
        getindex = model.index
        parents = set([os.path.dirname(z[0]) for z in dirs])
        self._t = PuddleThread(lambda: [getindex(z[0]) for z in dirs])
        def finished(indexes):
            for p in parents:
                if os.path.exists(p):
                    i = getindex(p)
                    model.refresh(i)
                    self.expand(i)
            for idx, (olddir,newdir) in zip(indexes, dirs):
                selectindex(getindex(newdir), QItemSelectionModel.Select)
            self._load = l
            mutex.unlock()
        self.connect(self._t, SIGNAL('threadfinished'), finished)
        mutex.lock(lambda x: self._t.start(), None)

    def selectDirs(self, dirlist):
        if not self._select:
            self._select = True
            qmutex.unlock()
            return
        load = self._load
        self._load = False
        if not dirlist:
            self._load = False
            self.selectionModel().clear()
            QApplication.processEvents()
            self._load = load
            return
        qmutex.lock()
        self.setEnabled(False)
        self.selectionModel().clear()
        selectindex = self.selectionModel().select
        getindex = self.model().index
        parent = self.model().parent

        def func():
            toselect = []
            toexpand = []
            for d in dirlist:
                index = getindex(d)
                toselect.append(index)
                i = parent(index)
                parents = []
                while i.isValid():
                    parents.append(i)
                    i = parent(i)
                toexpand.extend(parents)
            return (toselect, toexpand)

        def finished(val):
            select = val[0]
            expand = val[1]
            [selectindex(z, QItemSelectionModel.Select) for z in select]
            self.scrollTo(select[0], self.PositionAtCenter)
            [self.expand(z) for z in expand]
            self.blockSignals(False)
            self.setEnabled(True)
            self._load = load
            qmutex.unlock()
        self._dirthread = PuddleThread(func)
        self.connect(self._dirthread, SIGNAL('threadfinished'), finished)
        self._dirthread.start()

    def selectionChanged(self, selected, deselected):
        QTreeView.selectionChanged(self, selected, deselected)
        if not self._load:
            self._lastselection = len(self.selectedIndexes())
            return
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

control = ('Filesystem', DirView, LEFTDOCK, True)
