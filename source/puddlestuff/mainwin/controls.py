from PyQt4.QtGui import QApplication, QTreeView, QHeaderView, QSplitter, QDirModel, QComboBox, QLabel, QFrame, QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QWidget, QGridLayout, QDrag, QMenu
from PyQt4.QtCore import QDir, QPoint, Qt, QSize, SIGNAL, QMimeData, QUrl
from puddlestuff.puddleobjects import PuddleDock, PuddleThread, HeaderSetting
import puddlestuff.audioinfo as audioinfo
from puddlestuff.tagmodel import TagTable
from copy import deepcopy

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
            self.combos['genre'].addItems(sorted(TCON.GENRES))

    def reloadCombos(self, tags):
        self.setCombos(tags)

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
            if (event.pos() - pnt).manhattanLength() < QApplication.startDragDistance():
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
        """Use instead of setCurrentIndex for threaded index changing."""
        self.blockSignals(True)
        self.t = PuddleThread(lambda: self.model().index(filename))
        self.connect(self.t, SIGNAL('finished()'), self._setCurrentIndex)
        self.setEnabled(False)
        self.t.start()

    def _setCurrentIndex(self):
        self.setCurrentIndex(self.t.retval)
        self.resizeColumnToContents(0)
        self.setEnabled(True)
        self.blockSignals(False)

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
        (like when the app starts and settings are being restored).

        Call it with headerdata(as usual) to set the titles."""
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
        self.setFocus()

    def fillTable(self,folderpath, appendtags = False):
        """See TagTable's fillTable method for more details."""
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
