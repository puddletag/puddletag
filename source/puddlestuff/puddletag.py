#!/usr/bin/env python

"""
puddletag.py

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
import sys, audioinfo,os,findfunc, actiondlg, helperwin, pdb, puddlesettings, resource, ConfigParser
from copy import copy, deepcopy
from puddleobjects import ProgressWin, partial, safe_name, HeaderSetting, TableShit, unique, PuddleDock
(FILENAME, PATH, path) = (audioinfo.FILENAME, audioinfo.PATH, os.path)
from optparse import OptionParser
MSGARGS = (QMessageBox.Warning, QMessageBox.Yes or QMessageBox.Default,
                        QMessageBox.No or QMessageBox.Escape, QMessageBox.YesAll)

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
        self.tags = tags
        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)
        if tags is not None:
            self.setCombos(tags)

    def disableCombos(self):
        for z in self.combos:
            self.combos[z].clear()
            self.combos[z].setEnabled(False)

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
                self.combos[tagval] = QComboBox()
                self.combos[tagval].setInsertPolicy(QComboBox.NoInsert)
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
            self.combos[combo].clear()
            self.combos[combo].setEditable(True)
            self.combos[combo].addItems(["<keep>", "<blank>"])
            self.combos[combo].setEnabled(False)

        if 'genre' in self.combos:
            from mutagen.id3 import TCON
            self.combos['genre'].addItems(sorted(TCON.GENRES))

    def reloadCombos(self, tags):
        self.setCombos(tags)

class MyThread(QThread):
    def __init__(self, command, parent = None):
        QThread.__init__(self, parent)
        self.command = command
    def run(self):
        self.retval = self.command()


class DirView(QTreeView):
    """The treeview used to select a directory."""
    def __init__(self,parent = None):
        QTreeView.__init__(self,parent)
        self.header().setStretchLastSection(False)
        self.header().hide()


    def selectionChanged(self, selected, deselected):
        self.resizeColumnToContents(0)
        self.emit(SIGNAL("itemSelectionChanged()"))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.reject()

    def mouseMoveEvent(self, event):
        try:
            pnt = QPoint(*self.StartPosition)
            if (event.pos() - pnt).manhattanLength()  < QApplication.startDragDistance():
                return
            drag = QDrag(self)
            mimedata = QMimeData()
            mimedata.setUrls([QUrl(self.model().filePath(self.currentIndex()))])
            drag.setMimeData(mimedata)
            drag.setHotSpot(event.pos() - self.rect().topLeft())
            drag.start(Qt.MoveAction)
        except AttributeError:
            "No StartPosition, therefore no need to do dragging."

    def mousePressEvent(self, event):
        if event.buttons() == Qt.RightButton:
            self.contextMenuEvent(event)
        if event.buttons() == Qt.LeftButton:
            self.StartPosition = [event.pos().x(), event.pos().y()]
        QTreeView.mousePressEvent(self, event)
        self.resizeColumnToContents(0)

    def expand(self, index):
        self.resizeColumnToContents(0)
        QTreeView.expand(self, index)

    def setFileIndex(self, filename):
        self.t = MyThread(lambda: self.model().index(filename))
        self.connect(self.t, SIGNAL('finished()'), self._setCurrentIndex)
        self.setEnabled(False)
        self.t.start()

    def _setCurrentIndex(self):
        self.setCurrentIndex(self.t.retval)
        self.resizeColumnToContents(0)
        self.setEnabled(True)

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
        QHeaderView.mousePressEvent(self, event)

    def setTitles(self):
        if hasattr(self, "tags"):
            self.win = HeaderSetting(self.tags)
        else:
            self.win = HeaderSetting()
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


    def inittable(self, headerdata):
        """This is here, because I want to be able to initialize
        many of the tables values from other functions
        (like when the app starts and setting are being restored).

        Call it with headerdata(as usual) to set the titles."""
        self.table = TableShit(headerdata, self)
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
        sortedtag = deepcopy(self.headerdata[self.sortColumn])
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
        #FIXME: Using setFocus because the table isn't updated like it should be.
        #To see, load a folder, the load another folder with the same number of files.
        self.setFocus()

    def fillTable(self,folderpath, appendtags = False):
        """See TableShit's fillTable method for more details."""
        self.table.fillTable(folderpath, appendtags)
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


class MainWin(QMainWindow):
    """The brain of puddletag. Everything happens here."""
    def __init__(self):
        #Things to remember when editing this function:
        #1. If you add a QAction, add it to self.actions.
        #It's a list that's disabled and enabled depending on state of the app.
        #I also have a pretty bad convention of having action names in lower
        #case and the action's triggered() slot being the action name in
        #camelCase

        QMainWindow.__init__(self)

        #Shows or doesn't show path in titlebar of current folder
        self.pathinbar = False
        def connect(action, slot):
            self.connect(action, SIGNAL('triggered()'), slot)

        self.setWindowTitle("puddletag")
        self.cenwid = TableWindow()

        self.dirmodel = QDirModel()
        self.dirmodel.setSorting(QDir.IgnoreCase)
        self.dirmodel.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
        self.dirmodel.setReadOnly(False)

        self.tree = DirView()
        self.tree.setModel(self.dirmodel)
        [self.tree.hideColumn(column) for column in range(1,4)]
        self.tree.setDragEnabled(True)
        self.treedock = PuddleDock('Filesystem')
        self.treedock.setWidget(self.tree)
        self.treedock.layout().setAlignment(Qt.AlignTop)
        self.treedock.setObjectName('TreeDock')

        #Action for opening a folder
        self.opendir =  QAction(QIcon(':/open.png'), '&Open Folder...', self)
        self.opendir.setShortcut('Ctrl+O')
        connect(self.opendir, self.openFolder)

        #Action for adding another folder
        self.addfolder = QAction(QIcon(':/fileimport.png'), '&Add Folder...', self)
        connect(self.addfolder, self.addFolder)

        self.autotagging = QAction("Musicbrain&z", self)
        connect(self.autotagging, self.autoTagging)

        #Autonumbering shit
        self.changetracks = QAction(QIcon(':/track.png'), 'Autonumbering &Wizard...', self)
        connect(self.changetracks, self.trackWizard)

        self.cleartable = QAction("&Clear", self)
        connect(self.cleartable, self.clearTable)

        self.formattag = QAction("&Format Selected...", self)
        connect(self.formattag, self.formatValue)

        #Imports a file to read tags from.
        self.importfile = QAction(QIcon(":/import.png"), "Te&xt File -> Tag",self)
        connect(self.importfile, self.importFile)

        self.importlib = QAction("Import Music Library", self)
        connect(self.importlib, self.importLib)

        self.invertselection = QAction("&Invert selection", self)
        self.invertselection.setShortcut('Meta+I')

        self.openactions = QAction(QIcon(':/cap.png'), 'Ac&tions...', self)
        connect(self.openactions, self.openActions)

        self.preferences = QAction("&Preferences...", self)
        connect(self.preferences, self.openPrefs)

        self.actionvalue = partial(self.openActions, True)
        self.quickactions = QAction(QIcon(":/cap.png"), "&Quick Actions...", self)
        connect(self.quickactions, self.actionvalue)

        self.reloaddir = QAction("Reload", self)

        self.renamedir = QAction(QIcon(":/rename.png"), "&Rename Dir...",self)
        connect(self.renamedir, self.renameFolder)

        self.savecombotags = QAction(QIcon(':/save.png'), '&Save', self)
        self.savecombotags.setShortcut('Ctrl+S')
        connect(self.savecombotags, self.saveCombos)

        self.selectall = QAction("Select &All", self)
        self.selectall.setShortcut("Ctrl+A")

        self.showcombodock = QAction('Show Tag Editor', self)
        self.showcombodock.setCheckable(True)

        self.showfilter = QAction("Show Filter", self)
        self.showfilter.setCheckable(True)
        self.showfilter.setShortcut("F3")

        self.showlibrarywin = QAction('Show Library', self)
        self.showlibrarywin.setCheckable(True)
        self.showlibrarywin.setEnabled(False)

        self.showtreedock = QAction('Show Filesystem', self)
        self.showtreedock.setCheckable(True)

        #Action for importing tags from files
        self.tagfromfile = QAction(QIcon(':/filetotag.png'), '&File -> Tag', self)
        connect(self.tagfromfile, self.getTagFromFile)
        self.tagfromfile.setShortcut('Ctrl+F')

        self.tagtofile = QAction(QIcon(':/tagtofile.png'),
                                            'Tag -> &File', self)
        connect(self.tagtofile, self.saveTagToFile)
        self.tagtofile.setShortcut('Ctrl+T')

        self.undo = QAction("&Undo", self)
        self.undo.setShortcut("Ctrl+Z")

        self.patterncombo = QComboBox()
        self.patterncombo.setEditable(True)
        self.patterncombo.setToolTip("Enter a pattern here.")
        self.patterncombo.setStatusTip(self.patterncombo.toolTip())
        self.patterncombo.setMinimumWidth(500)
        self.patterncombo.setDuplicatesEnabled(False)

        self.toolbar = self.addToolBar("My Toolbar")
        self.toolbar.setObjectName("Toolbar")

        self.statusbar = self.statusBar()
        statuslabel = QLabel()
        statuslabel.setFrameStyle(QFrame.NoFrame)
        self.statusbar.addPermanentWidget(statuslabel,1)

        self.combogroup = FrameCombo()
        self.combogroup.setMinimumWidth(200)
        self.combodock = PuddleDock("Tag editor")
        self.combodock.setWidget(self.combogroup)
        self.combodock.setObjectName('Combodock')
        self.combodock.layout().setAlignment(Qt.AlignTop)

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Filter"))
        self.filtertable = QComboBox()
        self.filtertable.addItems(["None"] + audioinfo.INFOTAGS + sorted([z for z in audioinfo.REVTAGS]))
        self.filtertable.setEditable(True)
        self.filtertext = QLineEdit()
        hbox.addWidget(self.filtertable,0)
        hbox.setMargin(0)
        hbox.addWidget(self.filtertext,1)
        widget = QWidget(self)
        widget.setLayout(hbox)

        self.filterframe = PuddleDock("Filter", self)
        self.filterframe.setObjectName('Filter')
        self.filterframe.setWidget(widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.combodock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.treedock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.filterframe)

        self.setCentralWidget(self.cenwid)

        self.connect(self.filtertext, SIGNAL("textChanged(QString)"), self.filterTable)
        self.connect(self.filtertable, SIGNAL("editTextChanged(QString)"), self.filterTable)
        self.connect(self.statusbar,SIGNAL("messageChanged (const QString&)"), statuslabel.setText)

        self.loadInfo()

        menubar = self.menuBar()
        filemenu = menubar.addMenu('&File')
        [filemenu.addAction(z) for z in [self.opendir, self.addfolder,
        self.cenwid.table.play, self.savecombotags, self.cleartable, self.reloaddir]]
        filemenu.insertSeparator(self.savecombotags)

        edit = menubar.addMenu("&Edit")
        [edit.addAction(z) for z in [self.undo, self.cenwid.table.delete, self.showfilter, self.showcombodock,
        self.showtreedock, self.showlibrarywin, self.preferences]]
        edit.insertSeparator(self.showfilter)
        edit.insertSeparator(self.selectall)
        edit.insertSeparator(self.preferences)

        convert = menubar.addMenu("&Convert")
        [convert.addAction(z) for z in [self.tagfromfile, self.tagtofile, self.renamedir, self.importfile]]

        actionmenu = menubar.addMenu("&Actions")
        [actionmenu.addAction(z) for z in [self.openactions, self.quickactions, self.formattag]]

        toolmenu = menubar.addMenu("&Tools")
        [toolmenu.addAction(z) for z in [self.autotagging, self.cenwid.table.exttags, self.changetracks, self.importlib]]

        self.actions = [self.cenwid.table.delete, self.cenwid.table.play, self.cenwid.table.exttags,
                        self.tagfromfile, self.tagtofile, self.openactions, self.changetracks,
                        self.addfolder, self.renamedir, self.importfile,
                        self.quickactions, self.formattag, self.reloaddir, self.autotagging]

        self.supportactions = [self.undo, self.selectall, self.invertselection]

        self.toolbar.addAction(self.opendir)
        self.toolbar.addAction(self.savecombotags)
        self.toolbar.addWidget(self.patterncombo)
        [self.toolbar.addAction(action) for action in self.actions[3:]]

        connect(self.undo, self.cenwid.table.model().undo)
        connect(self.selectall, self.cenwid.table.selectAll)
        connect(self.invertselection, self.cenwid.table.invertSelection)

        self.connect(self.patterncombo, SIGNAL("editTextChanged(QString)"), self.patternChanged)
        self.connect(self.tree, SIGNAL('itemSelectionChanged()'), self.openTree)
        self.connect(self.cenwid.table, SIGNAL('itemSelectionChanged()'), self.rowEmpty)
        self.connect(self.cenwid.table, SIGNAL('removedRow()'), self.rowEmpty)
        self.connect(self.tree, SIGNAL('addFolder'), self.openFolder)
        self.connect(self.cenwid.table, SIGNAL('itemSelectionChanged()'),
                                         self.fillCombos)
        self.connect(self.cenwid.table, SIGNAL('setDataError'), self.statusbar.showMessage)

        #You'd think that this would cause recursion errors, but fortunately it doesn't
        self.connect(self.showfilter, SIGNAL("toggled(bool)"), self.filterframe.setVisible)
        self.connect(self.showcombodock, SIGNAL('toggled(bool)'), self.combodock.setVisible)
        self.connect(self.showtreedock, SIGNAL('toggled(bool)'), self.treedock.setVisible)
        self.connect(self.treedock, SIGNAL('visibilitychanged'), self.showtreedock.setChecked)
        self.connect(self.combodock, SIGNAL('visibilitychanged'), self.showcombodock.setChecked)
        self.connect(self.filterframe, SIGNAL('visibilitychanged'), self.showfilter.setChecked)

    def warningMessage(self, msg):
        QMessageBox.warning(self, 'Error', msg, QMessageBox.Ok, QMessageBox.NoButton)

    def writeError(self, filename, error, single):
        if single > 1:
            errormsg = u"I couldn't write to: <b>%s</b> (%s)<br /> Do you want to continue?" % \
                        (filename, error)
            mb = QMessageBox('Error', errormsg , *(MSGARGS + (self, )))
            ret = mb.exec_()
            if ret == QMessageBox.No:
                return False
            elif ret == QMessageBox.YesAll:
                return True
        else:
            self.warningMessage(u"I couldn't write to: <b>%s</b> (%s)" % (filename, error))

    def addFolder(self, filename = None):
        """Appends a folder. If filename is None, then show a dialog to
        open a folder first. Otherwise open the folder, filename"""
        if filename is None:
            self.openFolder(None, True)
        else:
            self.openFolder(filename, True)

    def autoTagging(self):
        """Opens Musicbrainz window"""
        from webdb import MainWin
        win = MainWin(self.cenwid.table, self)
        win.show()

    def changefocus(self):
        """Switches between different controls in puddletag, after user presses shortcut key."""
        controls = [self.cenwid.table, self.patterncombo]
        if self.combogroup.combos:
            #Found it by trial and error
            combo = self.combogroup.layout().itemAt(3).layout().itemAt(0).widget()
            controls.append(combo)
        if not hasattr(self, "currentfocus"):
            try:
                self.currentfocus = [i for i,control in enumerate(controls) if control.hasFocus()][0]
            except IndexError: #None of these control have focus
                self.currentfocus = len(controls) + 1
        if (self.currentfocus < (len(controls)-1)) :
            self.currentfocus += 1
        else:
            self.currentfocus = 0
        controls[self.currentfocus].setFocus()

    def clearTable(self):
        self.cenwid.table.model().taginfo = []
        self.cenwid.table.model().reset()
        self.fillCombos()

    def closeEvent(self, event):
        """Save settings and close."""
        settings = QSettings()
        cparser = puddlesettings.PuddleConfig(unicode(settings.fileName()))
        table = self.cenwid.table
        columnwidths = [unicode(table.columnWidth(z)) for z in range(table.model().columnCount())]
        cparser.setSection('editor', 'column', columnwidths)

        titles = [z[0] for z in self.cenwid.headerdata]
        tags = [z[1] for z in self.cenwid.headerdata]

        cparser.setSection('editor', 'titles', titles)
        cparser.setSection('editor', 'tags', tags)
        patterns = [unicode(self.patterncombo.itemText(z)) for z in xrange(self.patterncombo.count())]
        cparser.setSection('editor', 'patterns', patterns)

        settings.setValue("table/sortcolumn", QVariant(self.cenwid.sortColumn))
        settings.setValue("main/lastfolder", QVariant(self.lastFolder))
        settings.setValue("main/maximized", QVariant(self.isMaximized()))
        settings.setValue('main/state', QVariant(self.saveState()))

        settings.setValue('main/height', QVariant(self.height()))
        settings.setValue('main/width', QVariant(self.width()))

        settings.setValue("editor/showfilter",QVariant(self.filtertable.isVisible()))
        settings.setValue("editor/showcombo",QVariant(self.combodock.isVisible()))
        settings.setValue("editor/showtree",QVariant(self.treedock.isVisible()))

    def loadInfo(self):
        """Loads the settings from puddletags settings and sets it."""
        settings = QSettings()

        cparser = puddlesettings.PuddleConfig(unicode(QSettings().fileName()))
        puddlesettings.cparser = cparser

        self.lastFolder = cparser.load("main","lastfolder", unicode(QDir.homePath()))
        maximise = bool(cparser.load('main','maximized', True))

        self.setWindowState(Qt.WindowMaximized)
        height = settings.value('main/height', QVariant(600)).toInt()[0]
        width = settings.value('main/width', QVariant(800)).toInt()[0]
        self.resize(width, height)
        if maximise:
            self.setWindowState(Qt.WindowNoState)

        titles = cparser.load('editor', 'titles',
        ['Path', 'Artist', 'Title', 'Album', 'Track', 'Length', 'Year', 'Bitrate', 'Genre', 'Comment', 'Filename'])

        tags = cparser.load('editor', 'tags',
        ['__path', 'artist', 'title', 'album', 'track', '__length', 'date', '__bitrate', 'genre', 'comment', '__filename'])

        headerdata = []
        for title, tag in zip(titles, tags):
            headerdata.append((title,tag))

        self.cenwid.inittable(headerdata)
        self.connect(self.cenwid.table.model(), SIGNAL('enableUndo'), self.undo.setEnabled)
        self.connect(self.cenwid.table.model(), SIGNAL('dataChanged (const QModelIndex&,const QModelIndex&)'), self.fillCombos)
        self.connect(self.cenwid.table.model(), SIGNAL('dataChanged (const QModelIndex&,const QModelIndex&)'), self.filterTable)

        columnwidths = [int(z) for z in cparser.load("editor","column",[356, 190, 244, 206, 48, 52, 60, 100, 76, 304, 1191])]
        [self.cenwid.table.setColumnWidth(i, z) for i,z in enumerate(columnwidths)]

        sortColumn = cparser.load("Table","sortcolumn",1, True)
        self.cenwid.sortTable(int(sortColumn))

        #self.splitter.restoreState(settings.value("splittersize").toByteArray())
        puddlesettings.MainWin(self, readvalues = True)
        self.showcombodock.setChecked(settings.value("editor/showcombo",QVariant(True)).toBool())
        self.showtreedock.setChecked(settings.value("editor/showtree",QVariant(True)).toBool())
        #For some fucking reason I need to do this, otherwise filterframe is always loaded.
        showfilter = settings.value("editor/showfilter",QVariant(False)).toBool()
        self.showfilter.setChecked(showfilter)
        self.filterframe.setVisible(showfilter)
        self.restoreState(settings.value('main/state').toByteArray())

        self.connect(self.reloaddir, SIGNAL("triggered()"),self.reloadFiles)
        self.loadShortcuts()


    def displayTag(self, tag):
        """Used to display tags in the status bar with bolded tags."""
        if not tag:
            return "<b>Error in pattern</b>"
        s = "%s: <b>%s</b>, "
        return "".join([s % (z,v) for z,v in tag.items()])[:-2]

    def fillCombos(self, **args):
        """Fills the QComboBoxes in FrameCombo with
        the tags selected from self.table.

        It's **args, because many methods connect to fillCombos
        which pass arguments. None are needed."""

        table = self.cenwid.table
        combos = self.combogroup.combos

        if not hasattr(table, "selectedRows") or (table.rowCount() == 0) or not table.selectedRows:
            self.combogroup.disableCombos()
            return
        self.combogroup.initCombos()

        tags = dict([(tag,[]) for tag in combos])
        for row in table.selectedRows:
            audio = table.rowTags(row)
            for tag in tags:
                try:
                    if isinstance(audio[tag],(unicode, str)):
                        tags[tag].append(audio[tag])
                    else:
                        tags[tag].append("\\\\".join(audio[tag]))
                except KeyError:
                    tags[tag].append("")

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
            if (combo.count() > 3) or (combo.count() < 2):
                combo.setCurrentIndex(0)
            else:
                combo.setCurrentIndex(2)

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

        self.patternChanged()

    def filterTable(self, *args):
        """Filter the table. args are ignored,
        self.filtertables controls are used."""
        tag = unicode(self.filtertable.currentText())
        text = unicode(self.filtertext.text())
        if text == u"":
            tag = u"None"
        table = self.cenwid.table
        if tag == u"None":
            [table.showRow(z) for z in range(table.rowCount())]
        elif tag == u"__all":
            for z in range(table.rowCount()):
                table.hideRow(z)
                for y in table.rowTags(z).values():
                    if (y is not None) and (text in unicode(y)):
                        table.showRow(z)
                        break

        else:
            for z in range(table.rowCount()):
                if (tag in table.rowTags(z)) and (text in unicode(table.rowTags(z)[tag])):
                    table.showRow(z)
                else:
                    table.hideRow(z)

    def formatValue(self):
        """Show format value window."""
        if hasattr(self, "prevfunc"):
            f = actiondlg.CreateFunction(prevfunc = self.prevfunc, parent = self, showcombo = False)
        else:
            f = actiondlg.CreateFunction(parent = self, showcombo = False)
        f.setModal(True)
        f.show()
        self.connect(f, SIGNAL("valschanged"), self.formatValueBuddy)

    def formatValueBuddy(self, func):
        self.prevfunc = func
        table = self.cenwid.table
        win = ProgressWin(self, len(table.selectedRows), 10)
        headerdata = self.cenwid.headerdata
        showmessage = True

        for row in table.selectedRows:
            if win.wasCanceled(): break
            tags = {}
            rowtags = table.rowTags(row).stringtags()
            for column in table.selectedTags()[row]:
                try:
                    tags[headerdata[column][1]] = deepcopy(rowtags[headerdata[column][1]])
                except KeyError: #The key doesn't consist of any text
                    pass

            for tag in tags:
                try:
                    if func.function.func_code.co_varnames[0] == 'tags':
                        val = func.runFunction(rowtags)
                    else:
                        val = func.runFunction(tags[tag])
                    if val is not None:
                        tags[tag] = val
                except KeyError:
                    pass
            win.updateVal()
            try:
                self.setTag(row,tags)
            except (IOError, OSError), detail:
                if showmessage:
                    win.hide()
                    ret = self.writeError(table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))
                    if ret is False:
                        break
                    elif ret is True:
                        showmessage = False

        self.setTag(True)
        win.setValue(len(table.selectedRows))
        win.hide()
        win.close()
        self.fillCombos()

    def getTagFromFile(self, tag = None):
        """Get tags from the selected files using the pattern in
        self.pattercombo.
        If test = False then the tags are written.
        Otherwise the new tag of the first selected files is returned."""
        table = self.cenwid.table
        pattern = unicode(self.patterncombo.currentText())
        showmessage = True

        if not tag:
            win = ProgressWin(self, len(table.selectedRows), 10)
        else:
            return findfunc.filenametotag(pattern, path.basename(tag["__filename"]), True)

        for row in table.selectedRows:
            if win.wasCanceled(): break
            filename = table.rowTags(row)["__filename"]
            newtag = findfunc.filenametotag(pattern, path.basename(filename), True)
            try:
                if newtag is not None:
                    self.setTag(row, newtag)
                    win.updateVal()
            except (IOError, OSError), detail:
                if showmessage:
                    win.hide()
                    ret = self.writeError(table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))
                    if ret is False:
                        break
                    elif ret is True:
                        showmessage = False

        self.setTag(True)
        win.setValue(len(table.selectedRows))
        win.hide()
        win.close()
        self.fillCombos()


    def importFile(self):
        """Opens a text file so that tags can be
        read from it."""
        filedlg = QFileDialog()
        foldername = self.cenwid.table.rowTags(self.cenwid.table.selectedRows[0])["__folder"]
        filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder',foldername))

        if filename != "":
            win = helperwin.ImportWindow(self, filename)
            win.setModal(True)
            patternitems = [self.patterncombo.itemText(z) for z in range(self.patterncombo.count())]
            win.patterncombo.addItems(patternitems)
            self.connect(win,SIGNAL("Newtags"), self.importFileBuddy)
            self.fillCombos()

    def importFileBuddy(self, taglist):
        table = self.cenwid.table
        win = ProgressWin(self, len(table.selectedRows))
        showmessage = True
        for i, row in enumerate(table.selectedRows):
            if win.wasCanceled(): break
            try:
                self.setTag(row, taglist[i])
            except IndexError:
                break
            except (IOError, OSError), detail:
                if showmessage:
                    win.hide()
                    QApplication.processEvents()
                    ret = self.writeError(table.rowTags(row)[FILENAME], unicode(detail.strerror), len(taglist))
                    if ret is False:
                        break
                    elif ret is True:
                        showmessage = False
            win.updateVal()
        self.setTag(True)
        win.setValue(len(table.selectedRows))
        #win.hide()
        win.close()

    def importLib(self):
        """Shows window to import library."""
        from musiclib import MainWin
        win = MainWin(self)
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL('libraryAvailable'), self.loadLib)

    def loadLib(self, libclass):
        """Loads a music library. Creates tree and everything."""
        import musiclib
        if libclass:
            if not hasattr(self, 'librarywin'):
                self.librarywin = musiclib.LibraryWindow(libclass, self.cenwid.table.model().load, self)
                self.librarywin.setObjectName("LibraryDock")
                self.connect(self.showlibrarywin, SIGNAL('toggled(bool)'), self.librarywin.setVisible)
                self.connect(self.librarywin, SIGNAL('visibilitychanged'), self.showlibrarywin.setChecked)
                self.showlibrarywin.setEnabled(True)
                self.addDockWidget(Qt.RightDockWidgetArea, self.librarywin)
                self.connect(self.cenwid.table.model(),
                            SIGNAL('libraryFile'), self.librarywin.tree.filesEdited)
                self.connect(self.cenwid.table.model(),
                            SIGNAL('delLibFile'), self.librarywin.tree.delTracks)
            else:
                self.librarywin.loadLibrary(libclass, self.cenwid.table.model().load)
            self.librarywin.show()

    def loadShortcuts(self):
        """Used to load user defined shortcuts."""
        settings = QSettings()
        controls = {'table':self.cenwid.table,'patterncombo':self.patterncombo, 'main':self}
        size = settings.beginReadArray('Shortcuts')
        if size <= 0:
            settings = QSettings(":/puddletag.conf", QSettings.IniFormat)
            size = settings.beginReadArray('Shortcuts')

        for z in xrange(size):
            settings.setArrayIndex(z)
            control = "" #So that if control is defined incorrectly, no error is raised.
            try:
                control = controls[unicode(settings.value("control").toString())]
            except KeyError:
                val = unicode(settings.value("control").toString())
                if val.startswith("combo") and val[len('combo'):] in self.combogroup.combos:
                    control = self.combogroup.combos[val[len('combo'):]]
            command = unicode(settings.value("command").toString())
            key = settings.value("key").toString()
            if hasattr(control, command):
                QShortcut(key, self, getattr(control,command))
        settings.endArray()


    def openActions(self, quickaction = False):
        """Shows the action window and calls the corresponding
        method depending on the value of quickaction."""
        self.qb = actiondlg.ActionWindow(self.cenwid.headerdata, self)
        self.qb.setModal(True)
        self.qb.show()
        if quickaction:
            self.connect(self.qb, SIGNAL("donewithmyshit"), self.runQuickAction)
        else:
            self.connect(self.qb, SIGNAL("donewithmyshit"), self.runAction)

    def runAction(self, funcs):
        """Runs the action selected in openActions.

        funcs is a list of lists. Each list in turn consisting of
        actiondlg.Function objects. These are applied to
        the selected files.

        See the actiondlg module for more details on funcs."""
        table = self.cenwid.table
        win = ProgressWin(self, len(table.selectedRows), 10)
        showmessage = True
        for row in table.selectedRows:
            if win.wasCanceled(): break
            tags = table.rowTags(row).stringtags()
            edited = []
            for func in funcs:
                for infunc in func:
                    tag = infunc.tag
                    val = {}
                    if tag == ["__all"]:
                        tag = tags.keys()
                    if infunc.function.func_code.co_varnames[0] == 'tags':
                        for z in tag:
                            try:
                                val[z] = infunc.runFunction(tags)
                            except KeyError:
                                """The tag doesn't exist or is empty.
                                In either case we do nothing"""
                    else:
                        for z in tag:
                            try:
                                val[z] = infunc.runFunction(tags[z])
                            except KeyError:
                                """The tag doesn't exist or is empty.
                                In either case we do nothing"""

                    val = dict([z for z in val.items() if z[1]])
                    if val:
                        tags.update(val)
                        edited.extend(val)
            win.updateVal()
            mydict = dict([(z,tags[z]) for z in set(edited)])
            try:
                self.setTag(row, mydict)
            except (IOError, OSError), detail:
                if showmessage:
                    win.hide()
                    ret = self.writeError(table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))
                    if ret is False:
                        break
                    elif ret is True:
                        showmessage = False
        self.setTag(True)
        win.setValue(len(table.selectedRows)) #win doesn't close if it isn't
        #updated. Select five files or so and run this method without this line.
        win.hide()
        win.close()
        self.fillCombos()

    def runQuickAction(self, funcs):
        """Basically the same as runAction, except that
        all the functions in funcs are executed on the curently selected cells.

        Say you had a action that would convert "__path" to Mixed Case.
        If you ran it using runAction, it would do just that, but if you ran
        it using this function but had the title column selected, then
        all the files selected in the title column would have their titles
        converted to Mixed Case.

        funcs is a list of actiondlg.Function objects.
        No error checking is done, so don't pass shitty values."""

        table = self.cenwid.table
        win = ProgressWin(self, len(table.selectedRows), 10)
        headerdata = self.cenwid.headerdata
        showmessage = True

        for row in table.selectedRows:
            if win.wasCanceled(): break
            try:
                #looks complicated, but it's just the selected tags.
                selectedtags = table.rowTags(row).stringtags()
                tags = dict([(headerdata[column][1], selectedtags[headerdata[column][1]]) for column in table.selectedTags()[row]])
                for func in funcs:
                    for infunc in func:
                        for tag in tags:
                                if infunc.function.func_code.co_varnames[0] == 'tags':
                                    val = infunc.runFunction(selectedtags)
                                else:
                                    val = infunc.runFunction(tags[tag])
                                if val is not None:
                                    tags[tag] = val
                try:
                    self.setTag(row, tags)
                except (IOError, OSError), detail:
                    if showmessage:
                        win.hide()
                        ret = self.writeError(table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))
                        if ret is False:
                            break
                        elif ret is True:
                            showmessage = False

            except KeyError: #A tag doesn't exist, but needs to be read.
                pass
            win.updateVal()
        self.setTag(True)
        win.setValue(len(table.selectedRows))
        win.hide()
        win.close()
        self.fillCombos()

    def openFolder(self, filename = None, appenddir = False):
        """Opens a folder. If filename != None, then
        the table is filled with the folder.

        If filename is None, show the open folder dialog and open that.

        If appenddir = True, the folder is appended.
        Otherwise, the folder is just loaded."""
        import time
        t1 = time.time()
        selectionChanged = SIGNAL("itemSelectionChanged()")

        self.disconnect(self.tree, selectionChanged, self.openTree)
        self.disconnect(self.cenwid.table, selectionChanged, self.patternChanged)
        if filename is None:
            filedlg = QFileDialog()
            filedlg.setFileMode(filedlg.DirectoryOnly)
            filename = unicode(filedlg.getExistingDirectory(self,
                'OpenFolder', self.lastFolder ,QFileDialog.ShowDirsOnly))

        if len(filename) == 1:
            filename = filename[0]
        if type(filename) is unicode or type(filename) is str:
            if path.isdir(filename):
                #I'm doing this just to be safe.
                filename = path.realpath(filename)
                self.lastFolder = filename
                if not appenddir:
                    self.tree.setFileIndex(filename)
                    self.tree.resizeColumnToContents(0)
                if not self.isVisible():
                    #If puddletag is started via the command line with a
                    #large folder then the progress window is shown by itself without this window.
                    self.show()
                QApplication.processEvents()
                self.cenwid.fillTable(filename, appenddir)
                if self.pathinbar:
                    self.setWindowTitle("puddletag " + filename)
                else:
                    self.setWindowTitle("puddletag")
        else:
            self.cenwid.fillTable(filename, appenddir)
            self.setWindowTitle("Puddletag")

        self.connect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.connect(self.tree, selectionChanged, self.openTree)
        self.cenwid.table.setFocus()
        self.fillCombos()
        #print time.time() - t1

    def openPrefs(self):
        """Nothing much. Just opens a preferences window and shows it.
        The preferences windows does everything like setting of values, updating
        and so forth."""
        win = puddlesettings.MainWin(self, self)
        win.setModal(True)
        win.show()

    def openTree(self, filename = None):
        """If a folder in self.tree is clicked then it should be opened.

        If filename is not None, then nothing is opened. The currently
        selected index is just set to that filename."""
        selectionChanged = SIGNAL("itemSelectionChanged()")
        if filename is None:
            filename = unicode(self.dirmodel.filePath(self.tree.selectedIndexes()[0]))
            self.openFolder(filename)
        else:
            self.disconnect(self.tree, selectionChanged, self.openTree)
            index = self.dirmodel.index(filename)
            self.tree.setCurrentIndex(index)
            self.connect(self.tree, selectionChanged, self.openTree)


    def patternChanged(self):
        """This function is called everytime patterncombo changes.
        It sets the values of the StatusTips for various actions
        to a preview of the resulf if that action is hovered over."""
        #There's an error everytime an item is deleted, we account for that
        try:
            if hasattr(self.cenwid.table,'selectedRows'):
                tag = self.cenwid.table.rowTags(self.cenwid.table.selectedRows[0], True)
                self.tagfromfile.setStatusTip(self.displayTag(self.getTagFromFile(tag)))
                self.tagtofile.setStatusTip(unicode("New Filename: <b>") + self.saveTagToFile(tag) + '</b>')
                self.renamedir.setStatusTip(self.renameFolder(tag))
        except IndexError: pass

    def reloadFiles(self):
        selectionChanged = SIGNAL("itemSelectionChanged()")
        self.disconnect(self.tree, selectionChanged, self.openTree)
        self.disconnect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.cenwid.table.reloadFiles()
        self.connect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.connect(self.tree, selectionChanged, self.openTree)

    def renameFolder(self, tag = None):
        """Changes the directory of the currently selected files, to
        one as per the pattern in self.patterncombo.

        If a tag is passed, then nothing is done, but the new directory
        name using that tag is returned."""

        tagtofilename = findfunc.tagtofilename
        selectionChanged = SIGNAL('itemSelectionChanged()')
        table = self.cenwid.table
        showmessage = True

        if tag:
            oldir = os.path.dirname(tag['__folder'])
            newfolder = os.path.join(oldir, os.path.basename(tagtofilename(unicode(self.patterncombo.currentText()), tag)))
            return unicode("Rename: <b>") + tag["__folder"] + unicode("</b> to: <b>") + newfolder + u'</b>'

        dirname = os.path.dirname
        basename = os.path.basename
        path = os.path

        #Get distinct folders
        folders = [[row, table.rowTags(row)["__folder"]] for row in table.selectedRows]
        newdirs = []
        for z in folders:
            if z[1] not in (z[1] for z in newdirs):
                newdirs.append(z)

        self.disconnect(table, selectionChanged, self.patternChanged)
        self.disconnect(self.tree, selectionChanged, self.openTree)

        #Create the msgbox, I like that there'd be a difference between
        #the new and the old filename, so I bolded the new and italicised the old.
        msg = u"Are you sure you want to rename: <br />"
        dirs = []
        for z in newdirs:
            currentdir = z[1]
            newfolder = path.join(dirname(z[1]), (basename(tagtofilename(unicode(self.patterncombo.currentText()), table.rowTags(z[0])))))
            msg += u'<b>%s</b> to <i>%s</i><br /><br />' % (currentdir, newfolder)
            dirs.append([z[1], newfolder])

        msg = msg[:-len('<br /><br />')]

        #msgbox = QMessageBox("Rename dirs?", msg, QMessageBox.Question,
                            #QMessageBox.Yes or QMessageBox.Default,
                            #QMessageBox.No or QMessageBox.Escape, QMessageBox.NoButton, self)
        #msgbox.setTextFormat(Qt.RichText)
        #result = msgbox.exec_()

        result = QMessageBox.question(self, 'Rename dirs?', msg, "Yes","No", "" ,1, 1)

        #Compare function to sort directories via parent.
        #So that the parent is renamed before the child (Giving permission denied errors)
        def comp(a, b):
            if a == b:
                return 0
            elif a in b:
                return 1
            elif b in a:
                return -1
            elif len(a) > len(b):
                return 1
            elif len(b) > len(a):
                return -1
            elif len(b) == len(a):
                return 0

        from operator import itemgetter
        dirs = sorted(dirs, comp, itemgetter(0))

        #Finally, renaming
        if result == 0:
            for olddir, newdir in dirs:
                try:
                    idx = self.dirmodel.index(olddir)
                    os.rename(olddir, newdir)
                    self.cenwid.table.model().changeFolder(olddir, newdir)
                    self.dirmodel.refresh(self.dirmodel.parent(idx))
                    self.tree.setCurrentIndex(self.dirmodel.index(newdir))
                except (IOError, OSError), detail:
                    errormsg = u"I couldn't rename: <b>%s</b> to <i>%s</i> (%s)" % (olddir, newdir, unicode(detail.strerror))
                    if len(dirs) > 1:
                        if showmessage:
                            mb = QMessageBox('Error during rename', errormsg + u"<br />Do you want me to continue?", *(MSGARGS[:-1] + (QMessageBox.NoButton, self)))
                            ret = mb.exec_()
                            if ret == QMessageBox.Yes:
                                continue
                            if ret == QMessageBox.YesAll:
                                showmessage = False
                            else:
                                break
                    else:
                        self.warningMessage(u"I couldn't rename:<br /> <b>%s</b> to <i>%s</i> (%s)" % (olddir, newdir, unicode(detail.strerror)))
        self.connect(self.tree, selectionChanged, self.openTree)
        self.connect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.fillCombos()


    def rowEmpty(self):
        """If nothing's selected or if self.cenwid.table's empty,
        disable what needs to be disabled."""
        #An error gets raised if the table's empty.
        #So we disable everything in that case
        table = self.cenwid.table
        if table.isempty:
            [action.setEnabled(False) for action in self.supportactions]
        else:
            [action.setEnabled(True) for action in self.supportactions]

        try:
            if self.cenwid.table.selectedRows:
                [action.setEnabled(True) for action in self.actions]
                self.patterncombo.setEnabled(True)
                return
        except AttributeError:
                pass

        [action.setEnabled(False) for action in self.actions]
        self.patterncombo.setEnabled(False)

    def saveCombos(self):
        """Writes the tags of the selected files to the values in self.combogroup.combos."""
        combos = self.combogroup.combos
        table = self.cenwid.table
        if (not hasattr(table,'selectedRows')) or (not table.selectedRows):
            return
        win = ProgressWin(self, len(table.selectedRows), 10)
        showmessage = True

        self.disconnect(self.cenwid.table.model(), SIGNAL('dataChanged (const QModelIndex&,const QModelIndex&)'), self.fillCombos)
        for row in table.selectedRows:
            if win.wasCanceled(): break
            tags = {}
            for tag in combos:
                try:
                    curtext = unicode(combos[tag].currentText())
                    if curtext == "<blank>": tags[tag] = ""
                    elif curtext == "<keep>": pass
                    else:
                        tags[tag] = unicode(combos[tag].currentText()).split("\\\\")
                except KeyError:
                    pass
            win.updateVal()
            try:
                self.setTag(row, tags)
            except (IOError, OSError), detail:
                if showmessage:
                    win.hide()
                    ret = self.writeError(table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))
                    if ret is False:
                        break
                    elif ret is True:
                        showmessage = False
        self.setTag(True)
        win.setValue(len(table.selectedRows))
        self.connect(self.cenwid.table.model(), SIGNAL('dataChanged (const QModelIndex&,const QModelIndex&)'), self.fillCombos)
        win.hide()
        win.close()

    def saveTagToFile(self, tag = None):
        """Renames the selected files using the pattern
        in self.patterncombo.

        If tag is True then the files are not renamed and
        a new filename with using that tag is returned."""

        pattern = unicode(self.patterncombo.currentText())
        table = self.cenwid.table

        if not tag:
            win = ProgressWin(self, len(table.selectedRows), 10)
        else:
            #Just return an example value.
            newfilename = (findfunc.tagtofilename(pattern, tag, True,
                                                        tag["__ext"] ))
            return path.join(path.dirname(tag["__filename"]), safe_name(newfilename))

        taginfo = self.cenwid.tablemodel.taginfo
        pattern = unicode(self.patterncombo.currentText())
        showmessage = True
        showoverwrite = True
        for row in table.selectedRows:
            filename = taginfo[row][FILENAME]
            tag = taginfo[row]
            newfilename = (findfunc.tagtofilename(pattern,tag, True, tag["__ext"]))
            newfilename = path.join(path.dirname(filename), safe_name(newfilename))

            if path.exists(newfilename) and (newfilename != filename):
                win.show()
                if showoverwrite:
                    mb = QMessageBox('Ovewrite existing file?', "The file: " + newfilename + " exists. Should I overwrite it?",
                                    QMessageBox.Question, QMessageBox.Yes,
                                    QMessageBox.No or QMessageBox.Escape or QMessageBox.Default, QMessageBox.NoAll, self)
                    ret = mb.exec_()
                    if ret == QMessageBox.No:
                        continue
                    if ret == QMessageBox.NoAll:
                        showoverwrite = False
                        continue
                else:
                    continue
            try:
                self.setTag(row, {"__path": path.basename(newfilename)}, True)
            except (IOError, OSError), detail:
                if showmessage:
                    win.show()
                    errormsg = u"I couldn't rename <b>%s<b> to <i>%s</i> (%s)" \
                                 % (filename, newfilename, unicode(detail.strerror))
                    if len(table.selectedRows) > 1:
                        errormsg += "<br /> Do you want to continue?"
                        mb = QMessageBox('Renaming Failed', errormsg , *(MSGARGS + (self,)))
                        ret = mb.exec_()
                        if ret == QMessageBox.No:
                            break
                        elif ret == QMessageBox.YesAll:
                            showmessage = False
                    self.warningMessage(errormsg)

            win.updateVal()
        self.setTag(True)
        win.setValue(len(table.selectedRows))
        self.fillCombos()
        win.hide()
        win.close()


    def setTag(self, row, tag = None, rename = False):
        """Used to write tags.

        row is the the row that's to be written to. If it
        is True, then nothing is written and the undolevel is updated.
        tag is a tag as normal
        if rename is True, then just renaming is done(for speed)

        Call this function if you have many files to write to and
        you want them all to have the same undo level. Make sure
        to call it with row = True afterwards.
        """
        table = self.cenwid.table
        if row is not True:
            rowtags = table.rowTags(row)

        if row is True and hasattr(self, 'librarywin'):
            self.librarywin.tree.cacheFiles(True)
        elif (row is not True) and ('__library' in rowtags):
            newfile = rowtags.tags.copy()
            newfile.update(tag)
            self.librarywin.tree.cacheFiles([rowtags.tags.copy()],
                                                [newfile])

        if row is True:
            table.model().undolevel += 1
            return
        level = table.model().undolevel
        mydict = {}
        #Create undo level for file
        try:
            for z in tag:
                if z not in rowtags:
                    mydict[z] = ""
                else:
                    mydict[z] = deepcopy(rowtags[z])
            tag[level] = mydict
        except TypeError: #If tag is None, or not a dictionary
            return
        table.updateRow(row, tag, justrename = rename)

    def trackWizard(self):
        """Shows the autonumbering wizard and sets the tracks
            numbers should be filled in"""

        selectedRows = self.cenwid.table.selectedRows
        numtracks = len(selectedRows)
        rowTags = self.cenwid.table.rowTags
        tags = [rowTags(row, True) for row in selectedRows]

        from puddleobjects import compare, itemgetter
        cmpfunc = compare().natcasecmp
        for tag in tags:
            if 'track' not in tags:
                tag['track'] = ""
        mintrack = sorted(tags, cmpfunc, key = itemgetter("track"))[0]["track"]

        try:
            if "/" in mintrack:
                enablenumtracks = True
                mintrack = long(mintrack.split("/")[0])
            else:
                enablenumtracks = False
                mintrack = long(mintrack)
        except ValueError:
            mintrack = 1

        win = helperwin.TrackWindow(self, mintrack, numtracks, enablenumtracks)
        win.setModal(True)
        self.connect(win, SIGNAL("newtracks"), self.numberTracks)
        win.show()

    def numberTracks(self, indexes):
        """Numbers the selected tracks sequentially in the range
        between the indexes.
        The first item of indices is the starting track.
        The second item of indices is the number of tracks."""
        fromnum = indexes[0]
        if indexes[1] != "":
            num = "/" + indexes[1]
        else: num = ""

        table = self.cenwid.table
        rows = table.selectedRows
        showmessage = True
        win = ProgressWin(self, len(rows), table)

        if indexes[2]: #Restart dir numbering
            rowTags = table.rowTags
            folders = {}
            taglist = []
            for row in rows:
                folder = rowTags(row)["__folder"]
                if folder in folders:
                    folders[folder] += 1
                else:
                    folders[folder] = fromnum
                taglist.append({"track": unicode(folders[folder]) + num})
        else:
            taglist = [{"track": unicode(z) + num} for z in range(fromnum, fromnum + len(rows) + 1)]

        for i, row in enumerate(rows):
            if win.wasCanceled(): break
            try:
                self.setTag(row, taglist[i])
            except IndexError:
                break
            except (IOError, OSError), detail:
                if showmessage:
                    win.hide()
                    ret = self.writeError(table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))
                    if ret is False:
                        break
                    elif ret is True:
                        showmessage = False
            win.updateVal()
        self.setTag(True)
        win.setValue(len(table.selectedRows))
        win.hide()
        win.close()
        self.fillCombos()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    filename = sys.argv[1:]
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")

    qb = MainWin()
    qb.rowEmpty()
    if filename:
        pixmap = QPixmap(':/puddlelogo.png')
        splash = QSplash(pixmap)
        splash.show()
        QApplication.processEvents()
        qb.openFolder(filename)
    qb.show()
    app.exec_()
