from PyQt4.QtGui import QAction, QIcon
from controls import *
from puddlestuff.puddleobjects import partial

def createActions(parent):
        #Things to remember when editing this function:
        #1. If you add a QAction, add it to parent.actions.
        #It's a list that's disabled and enabled depending on state of the app.
        #I also have a pretty bad convention of having action names in lower
        #case and the action's triggered() slot being the action name in
        #camelCase

        #Action for opening a folder
        parent.opendir =  QAction(QIcon(':/open.png'), '&Open Folder...', parent)
        parent.opendir.setShortcut('Ctrl+O')

        #Action for adding another folder
        parent.addfolder = QAction(QIcon(':/fileimport.png'), '&Add Folder...', parent)
        parent.autotagging = QAction("Musicbrain&z", parent)
        #Autonumbering Wizard
        parent.changetracks = QAction(QIcon(':/track.png'), 'Autonumbering &Wizard...', parent)
        parent.cleartable = QAction("&Clear", parent)
        parent.formattag = QAction("&Format", parent)
        parent.puddlefunctions = QAction('Functions...', parent)
        parent.importfile = QAction(QIcon(":/import.png"), "Te&xt File -> Tag",parent)
        parent.importlib = QAction("Import Music Library", parent)
        parent.invertselection = QAction("&Invert selection", parent)
        parent.invertselection.setShortcut('Meta+I')
        parent.openactions = QAction(QIcon(':/cap.png'), 'Ac&tions...', parent)
        parent.preferences = QAction("&Preferences...", parent)
        parent.quickactions = QAction(QIcon(":/quickactions.png"), "&Quick Actions...", parent)
        parent.reloaddir = QAction(QIcon(':/reload.png'), "Reload", parent)
        parent.renamedir = QAction(QIcon(":/rename.png"), "&Rename Dir...",parent)
        parent.savecombotags = QAction(QIcon(':/save.png'), '&Save', parent)
        parent.savecombotags.setShortcut('Ctrl+S')
        parent.selectall = QAction("Select &All", parent)
        parent.selectall.setShortcut("Ctrl+A")
        parent.selectcolumn = QAction('Select Current Column', parent)
        parent.selectcolumn.setShortcut('Meta+C')
        parent.showcombodock = QAction('Show Tag Editor', parent)
        parent.showcombodock.setCheckable(True)
        parent.showfilter = QAction("Filter", parent)
        parent.showfilter.setCheckable(True)
        parent.showfilter.setShortcut("F3")
        parent.showlibrarywin = QAction('Library', parent)
        parent.showlibrarywin.setCheckable(True)
        parent.showlibrarywin.setEnabled(False)
        parent.showtreedock = QAction('Filesystem', parent)
        parent.showtreedock.setCheckable(True)
        parent.tagfromfile = QAction(QIcon(':/filetotag.png'), 'File -> &Tag', parent)
        parent.tagfromfile.setShortcut('Ctrl+T')
        parent.tagtofile = QAction(QIcon(':/tagtofile.png'),
                                            'Tag -> &File', parent)
        parent.tagtofile.setShortcut('Ctrl+F')
        parent.undo = QAction(QIcon(':/undo.png'), "&Undo", parent)
        parent.undo.setShortcut("Ctrl+Z")
        parent.undo.setEnabled(False)
        parent.duplicates = QAction('Show dupes', parent)
        parent.duplicates.setCheckable(True)
        parent.fileinlib = QAction('In library?', parent)
        parent.fileinlib.setCheckable(True)
        parent.cutaction = QAction(QIcon(':/cut.png'), '&Cut Selected', parent)
        parent.cutaction.setShortcut('Ctrl+X')
        parent.copyaction = QAction(QIcon(':/copy.png'),'C&opy Selected', parent)
        parent.copyaction.setShortcut('Ctrl+C')
        parent.pasteaction = QAction(QIcon(':/paste.png'), '&Paste Onto Selected', parent)
        parent.pasteaction.setShortcut('Ctrl+V')

def connectActions(parent):
    def connect(action, slot):
            parent.connect(action, SIGNAL('triggered()'), slot)
    connect(parent.changetracks, parent.trackWizard)
    connect(parent.addfolder, parent.addFolder)
    connect(parent.opendir, parent.openFolder)
    connect(parent.autotagging, parent.autoTagging)
    connect(parent.cleartable, parent.clearTable)
    connect(parent.formattag, parent.formatValue)
    connect(parent.puddlefunctions, parent.puddleFunctions)
    connect(parent.importfile, parent.importFile)
    connect(parent.importlib, parent.importLib)
    connect(parent.openactions, parent.openActions)
    connect(parent.preferences, parent.openPrefs)
    parent._actionvalue = partial(parent.openActions, True)
    connect(parent.quickactions, parent._actionvalue)
    connect(parent.renamedir, parent.renameFolder)
    connect(parent.savecombotags, parent.saveCombos)
    connect(parent.tagfromfile, parent.getTagFromFile)
    connect(parent.tagtofile, parent.saveTagToFile)
    parent.connect(parent.duplicates, SIGNAL('toggled(bool)'), parent.showDupes)
    parent.connect(parent.fileinlib, SIGNAL('toggled(bool)'), parent.inLib)
    parent.connect(parent.filtertext, SIGNAL("textChanged(QString)"), parent.filterTable)
    parent.connect(parent.filtertable, SIGNAL("editTextChanged(QString)"), parent.filterTable)

    table = parent.cenwid.table
    connect(parent.undo, table.model().undo)
    connect(parent.selectall, table.selectAll)
    connect(parent.invertselection, table.invertSelection)
    connect(parent.selectcolumn, table.selectCurrentColumn)
    connect(parent.cutaction, parent.cut)
    connect(parent.pasteaction, parent.paste)
    connect(parent.copyaction, parent.clipcopy)

    parent.connect(parent.patterncombo, SIGNAL("editTextChanged(QString)"), parent.patternChanged)
    parent.connect(parent.tree, SIGNAL('itemSelectionChanged()'), parent.openTree)
    parent.connect(table, SIGNAL('itemSelectionChanged()'), parent.rowEmpty)
    parent.connect(table, SIGNAL('removedRow()'), parent.rowEmpty)
    parent.connect(parent.tree, SIGNAL('addFolder'), parent.openFolder)
    parent.connect(table, SIGNAL('itemSelectionChanged()'),
                                        parent.fillCombos)
    parent.connect(table, SIGNAL('setDataError'), parent.statusBar().showMessage)

    #You'd think that this would cause recursion errors, but fortunately it doesn't.
    parent.connect(parent.showfilter, SIGNAL("toggled(bool)"), parent.filterframe.setVisible)
    parent.connect(parent.showcombodock, SIGNAL('toggled(bool)'), parent.combodock.setVisible)
    parent.connect(parent.showtreedock, SIGNAL('toggled(bool)'), parent.treedock.setVisible)
    parent.connect(parent.treedock, SIGNAL('visibilitychanged'), parent.showtreedock.setChecked)
    parent.connect(parent.combodock, SIGNAL('visibilitychanged'), parent.showcombodock.setChecked)
    parent.connect(parent.filterframe, SIGNAL('visibilitychanged'), parent.showfilter.setChecked)

def createMenus(parent):
    table = parent.cenwid.table
    separator = QAction(parent)
    separator.setSeparator(True)
    table.actions.extend([separator, parent.copyaction, parent.cutaction, parent.pasteaction])

    menubar = parent.menuBar()
    filemenu = menubar.addMenu('&File')
    [filemenu.addAction(z) for z in [parent.opendir, parent.addfolder,
    table.play, separator, parent.savecombotags, parent.reloaddir, parent.cleartable]]

    edit = menubar.addMenu("&Edit")
    table = parent.cenwid.table
    [edit.addAction(z) for z in [parent.undo, separator, parent.cutaction,
        parent.copyaction, parent.pasteaction, separator, table.delete, separator,
        parent.selectall, parent.invertselection, parent.selectcolumn, separator,
                                                parent.preferences]]

    convert = menubar.addMenu("&Convert")
    [convert.addAction(z) for z in [parent.tagfromfile, parent.tagtofile,
                parent.formattag, separator, parent.renamedir, parent.importfile]]

    actionmenu = menubar.addMenu("&Actions")
    [actionmenu.addAction(z) for z in [parent.openactions, parent.quickactions, parent.puddlefunctions]]

    toolmenu = menubar.addMenu("&Tools")
    [toolmenu.addAction(z) for z in [parent.autotagging, table.exttags,
            parent.changetracks, parent.importlib, separator, parent.fileinlib, parent.duplicates]]

    winmenu = menubar.addMenu('&Windows')
    [winmenu.addAction(z) for z in (parent.showfilter, parent.showcombodock,
                                    parent.showtreedock, parent.showlibrarywin)]

    parent.actions = [table.delete, table.play, table.exttags,
                    parent.cutaction, parent.copyaction, parent.pasteaction,
                    parent.savecombotags, parent.tagfromfile,
                    parent.tagtofile, parent.formattag,
                    parent.openactions, parent.quickactions, parent.puddlefunctions,
                    parent.changetracks, parent.importfile, parent.renamedir, parent.autotagging]

    parent.supportactions = [parent.selectall, parent.invertselection, parent.selectcolumn,
        parent.duplicates, parent.fileinlib, parent.addfolder, parent.reloaddir]

    [parent.toolbar.addAction(z) for z in (parent.opendir, parent.addfolder,
                    parent.reloaddir, separator, parent.savecombotags, parent.undo,
                    separator)]
    #[parent.toolbar.addAction(z) for z in (parent.cutaction, parent.pasteaction, parent.copyaction)]
    #parent.toolbar.addSeparator()
    parent.toolbar.addWidget(parent.patterncombo)
    [parent.toolbar.addAction(action) for action in parent.actions[7:] + [parent.fileinlib, parent.duplicates]]
    parent.toolbar.insertSeparator(parent.openactions)
    parent.toolbar.insertSeparator(parent.changetracks)
    parent.toolbar.insertSeparator(parent.fileinlib)

def createControls(parent):
    parent.cenwid = TableWindow()

    parent.dirmodel = QDirModel()
    parent.dirmodel.setSorting(QDir.IgnoreCase)
    parent.dirmodel.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
    parent.dirmodel.setReadOnly(True)
    parent.dirmodel.setLazyChildCount(True)

    parent.tree = DirView()
    parent.tree.setModel(parent.dirmodel)
    [parent.tree.hideColumn(column) for column in range(1,4)]
    parent.tree.setDragEnabled(True)
    parent.treedock = PuddleDock('Filesystem')
    parent.treedock.setWidget(parent.tree)
    parent.treedock.layout().setAlignment(Qt.AlignTop)
    parent.treedock.setObjectName('TreeDock')

    parent.patterncombo = QComboBox()
    parent.patterncombo.setEditable(True)
    parent.patterncombo.setToolTip("Enter a pattern here.")
    parent.patterncombo.setStatusTip(parent.patterncombo.toolTip())
    parent.patterncombo.setMinimumWidth(500)
    parent.patterncombo.setDuplicatesEnabled(False)

    parent.combogroup = FrameCombo()
    parent.combogroup.setMinimumWidth(200)
    parent.combodock = PuddleDock("Tag editor")
    parent.combodock.setWidget(parent.combogroup)
    parent.combodock.setObjectName('Combodock')
    parent.combodock.layout().setAlignment(Qt.AlignTop)

    hbox = QHBoxLayout()
    hbox.addWidget(QLabel("Tag"))
    parent.filtertable = QComboBox()
    parent.filtertable.addItems(["None", '__all'] + audioinfo.INFOTAGS + sorted([z for z in audioinfo.REVTAGS]))
    parent.filtertable.setEditable(True)
    parent.filtertext = QLineEdit()
    hbox.addWidget(parent.filtertable,0)
    hbox.setMargin(0)
    hbox.addWidget(parent.filtertext,1)
    widget = QWidget(parent)
    widget.setLayout(hbox)

    parent.filterframe = PuddleDock("Filter", parent)
    parent.filterframe.setObjectName('Filter')
    parent.filterframe.setWidget(widget)
    parent.addDockWidget(Qt.LeftDockWidgetArea, parent.combodock)
    parent.addDockWidget(Qt.LeftDockWidgetArea, parent.treedock)
    parent.addDockWidget(Qt.BottomDockWidgetArea, parent.filterframe)

    parent.setCentralWidget(parent.cenwid)

    parent.toolbar = parent.addToolBar("My Toolbar")
    parent.toolbar.setIconSize(QSize(16,16))
    parent.toolbar.setObjectName("Toolbar")
