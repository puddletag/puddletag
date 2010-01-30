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
        self._mapping = {}
        self._revmapping = {}
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

        tags = dict([(self._revmapping[tag],[]) if tag in self._revmapping else (tag,[]) for tag in combos if tag != '__image'])
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
            if tagset in self._mapping:
                [combos[self._mapping[tagset]].addItem(unicode(z)) for z in sorted(tags[tagset])
                        if combos.has_key(tagset)]
            else:
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

    def setMapping(self, mapping,revmapping):
        self._mapping = mapping
        self._revmapping = {}

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
        self.table = TagTable(parent=self)
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)
        header = self.table.horizontalHeader()

        self.inittable=self.setNewHeader

    def setNewHeader(self, tags):
        """Used for 'hotswapping' of the table header.

        If you want to set the table header while the app
        is running, then this is the methods you should use.

        tags are a list of tags defined as usual(See FrameCombo's docstring).

        Nothing is returned, if the function is successful, then you should
        see the correct results."""

        self.table.model().setHeader(tags)

    def sortTable(self,column):
        self.sortColumn = column
        self.table.sortByColumn(column)
        self.setFocus()

    def setGridVisible(self, val):
        self.table.setShowGrid(val)

    def getGridVisible(self):
        return self.table.showGrid()

    gridvisible = property(getGridVisible, setGridVisible)
