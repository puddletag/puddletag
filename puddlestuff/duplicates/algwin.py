import os
import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import QAction, QApplication, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, \
    QInputDialog, QLabel, QLineEdit, QMessageBox, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, \
    QWidget

from .dupefuncs import dupesinlib
from .matchfuncs import Algo, funcinfo, funcs, _ratio
from ..constants import SAVEDIR, RIGHTDOCK
from ..findfunc import tagtofilename
from ..puddletag import add_shortcuts
from ..puddleobjects import ListButtons, ListBox, OKCancel, PuddleConfig
from ..puddleobjects import get_icon, progress, winsettings

title_sort = lambda a: a.get('title', '')
dupe_sort = lambda a: a[0].get('title', '')

DEFAULTSET = {'setname': 'Default',
              'algs': [Algo(['artist', 'title'], 0.85, _ratio, False)],
              'disp': ['%artist%', '%artist% - %title%'],
              'maintag': 'artist'}

DUPEDIR = os.path.join(SAVEDIR, 'dupes')


def saveset(setname, disp, algs, maintag):
    cparser = PuddleConfig()
    filename = os.path.join(DUPEDIR, setname)
    open(filename, 'w').close()  # I have to clear the file because if a previous
    # set had more algos then the extra algos will get loaded.
    cparser.filename = filename
    algs = [{'tags': a.tags, 'threshold': a.threshold,
             'func': a.func.__name__, 'matchcase': a.matchcase,
             'maintag': maintag} for a in algs]

    cparser.set('info', 'name', setname)
    cparser.set('info', 'disp', disp)
    for i, a in enumerate(algs):
        setname = 'alg' + str(i)
        for key, val in a.items():
            cparser.set(setname, key, val)


def loadsets():
    algos = []
    if not os.path.exists(DUPEDIR):
        os.makedirs(DUPEDIR)
        saveset(**DEFAULTSET)
    files = [os.path.join(DUPEDIR, z) for z in os.listdir(DUPEDIR)]
    sets = []

    cparser = PuddleConfig()
    for f in files:
        cparser.filename = f
        name = cparser.get('info', 'name', '')
        disp = cparser.get('info', 'disp', [])
        algos = []
        for section in cparser.sections():
            if section == 'info':
                continue
            tags = cparser.get(section, 'tags', [])
            threshold = float(cparser.get(section, 'threshold', '0.85'))
            func = cparser.get(section, 'func', '')
            matchcase = cparser.get(section, 'matchcase', True)
            maintag = cparser.get(section, 'maintag', 'artist')
            algos.append(Algo(tags, threshold, func, matchcase))
        sets.append([name, disp, algos, maintag])
    return sets


class DupeTree(QTreeWidget):
    loadtags = pyqtSignal(list, name='loadtags')
    toplevel = pyqtSignal('QTreeWidgetItem', name='toplevel')

    def __init__(self, *args, **kwargs):
        QTreeWidget.__init__(self, *args)
        self.emits = ['loadtags']
        self.receives = []

    def selectedFiles(self):
        total = []
        for item in self.selectedItems():
            tracks = []
            parent = item.parent()
            if parent and parent not in self.selectedItems():
                index = parent.indexOfChild(item)
                children = item.childCount()
                if children:
                    parindex = self.indexOfTopLevelItem(parent)
                    tracks = self.dupes[parindex][index]
                else:
                    topindex = self.indexOfTopLevelItem(parent.parent())
                    parindex = parent.parent().indexOfChild(parent)
                    tracks = [self.dupes[topindex][parindex][index]]
            elif not parent:
                index = self.indexOfTopLevelItem(item)
                [tracks.extend(z) for z in self.dupes[index]]
            total.extend(tracks)
        return total

    def selectionChanged(self, selected, deselected):
        QTreeWidget.selectionChanged(self, selected, deselected)
        self.loadtags.emit(self.selectedFiles())

    def loadDupes(self, lib, algos, dispformat, maintag='artist'):
        self.clear()
        dupes = dupesinlib(lib, algos, maintag=maintag)
        self.dupes = []
        artists = next(dupes)

        def what():
            for i, d in enumerate(dupes):
                a = artists[i]
                if d:
                    self.dupes.append(d)
                    item = QTreeWidgetItem([a])
                    for z in sorted(d, key=dupe_sort):
                        child = QTreeWidgetItem([tagtofilename(dispformat[0], z[0])])
                        item.addChild(child)
                        [child.addChild(QTreeWidgetItem([
                            tagtofilename(dispformat[1], x)])) for x in
                            sorted(z[1:], key=title_sort)]
                    self.toplevel.emit(item)
                yield None

        s = progress(what, 'Checking ', len(artists))
        self.toplevel.connect(self._addItem)
        if self.parentWidget():
            s(self.parentWidget())
        else:
            s(self)

    def _addItem(self, item):
        self.addTopLevelItem(item)

    def dragEnterEvent(self, event):
        event.reject()

    # def mouseMoveEvent(self, event):
    # QTreeWidget.mouseMoveEvent(self, event)
    # if event.buttons() != Qt.MouseButton.LeftButton:
    # return
    # mimeData = QMimeData()
    # plainText = ""
    # tags= []
    # pnt = QPoint(*self.StartPosition)
    # if (event.pos() - pnt).manhattanLength()  < QApplication.startDragDistance():
    # return
    ##I'm adding plaintext to MimeData
    ##because XMMS doesn't seem to work well with Qt's URL's
    # for z in self.selectedFiles():
    # url = QUrl.fromLocalFile(z['__filename'])
    # plainText = plainText + unicode(url.toString()) + "\n"
    # tags.append(url)
    # mimeData = QMimeData()
    # mimeData.setUrls(tags)
    # mimeData.setText(plainText)

    # drag = QDrag(self)
    # drag.setDragCursor(QPixmap(), self.dropaction)
    # drag.setMimeData(mimeData)
    # drag.setHotSpot(event.pos() - self.rect().topLeft())
    # dropaction = drag.exec_(self.dropaction)

    # def mousePressEvent(self, event):
    # if event.buttons() == Qt.MouseButton.RightButton:
    # e = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, event.pos(), event.globalPos())
    # self.contextMenuEvent(e)
    # return
    # if event.buttons() == Qt.MouseButton.LeftButton:
    # self.StartPosition = [event.pos().x(), event.pos().y()]
    # QTreeWidget.mousePressEvent(self, event)

    # def contextMenuEvent(self, event):
    # menu = QMenu(self)
    # move = QAction('Move duplicates', self)
    # delete = QAction('Delete duplicates', self)
    # remove = QAction('Remove from listing', self)

    # delete.triggered.connect(self._move)
    # create.triggered.connect(self._delete)
    # rename.triggered.connect(self._remove)
    # [menu.addAction(z) for z in [move, remove, delete]]
    # menu.exec_(event.globalPos())

    # def _remove(self):
    # pass

    # def _delete(self):
    # pass

    # def _move(self):
    # pass


class AlgWin(QWidget):
    okCLickedSignal = pyqtSignal(Algo, name='okClicked')

    def __init__(self, parent=None, alg=None):
        QWidget.__init__(self, parent)
        winsettings('algwin', self)
        taglabel = QLabel('&Tags')
        self.tags = QLineEdit('artist | title')
        taglabel.setBuddy(self.tags)
        self.alcombo = QComboBox()
        allabel = QLabel('&Algorithms')
        allabel.setBuddy(self.alcombo)
        self.threshold = QLineEdit('90')
        self.threshold.setValidator(QDoubleValidator(self.threshold))
        perlabel = QLabel("&Match threshold")
        perlabel.setBuddy(self.threshold)

        self.matchcase = QCheckBox('&Match Case')

        okcancel = OKCancel()
        okcancel.okButton.setDefault(True)

        okcancel.ok.connect(self.okClicked)
        okcancel.cancel.connect(self.close)

        vbox = QVBoxLayout()
        [vbox.addWidget(z) for z in [taglabel, self.tags, perlabel, self.threshold,
                                     allabel, self.alcombo, self.matchcase]]
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setLayout(vbox)

        box = QVBoxLayout()
        box.addWidget(frame)
        box.addLayout(okcancel)
        self.setLayout(box)

        x = [funcinfo(z) for z in funcs]
        names = [z[0] for z in x]
        ds = [z[1] for z in x]

        self.alcombo.clear()
        self.alcombo.addItems(names)
        self.alcombo.setCurrentIndex(0)
        tooltip = "<dl>%s</dl>" % ''.join(['<dt><b>%s<b></dt> <dd>%s</dd>' % z for z in x])
        self.alcombo.setToolTip(tooltip)
        if alg:
            self.loadAlgo(alg)

    def loadAlgo(self, alg):
        i = self.alcombo.findText(alg.funcname)
        if i >= 0:
            self.alcombo.setCurrentIndex(i)
        else:
            self.alcombo.addItem(alg.funcname)
            self.alcombo.setCurrentIndex(self.alcombo.count() - 1)

        self.tags.setText(' | '.join(alg.tags))
        self.threshold.setText('%.2f' % (alg.threshold * 100))
        if alg.matchcase:
            self.matchcase.setCheckState(Qt.CheckState.Checked)
        else:
            self.matchcase.setCheckState(Qt.CheckState.Unchecked)

    def saveAlgo(self):
        tags = [x for x in [z.strip() for z in str(self.tags.text()).split("|")] if x != ""]
        func = funcs[self.alcombo.currentIndex()]
        threshold = float(str(self.threshold.text())) / 100
        matchcase = False
        if self.matchcase.checkState() == Qt.CheckState.Checked:
            matchcase = True

        return Algo(tags, threshold, func, matchcase)

    def okClicked(self):
        self.okClickedSignal.emit(self.saveAlgo())
        self.close()


class SetDialog(QDialog):
    setAvailable = pyqtSignal(list, name='setAvailable')

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        winsettings('setdialog', self)
        vbox = QVBoxLayout()
        self._previndex = 0
        self.setscombo = QComboBox()
        setlabel = QLabel('&Sets')
        setlabel.setBuddy(self.setscombo)
        vbox.addWidget(setlabel)

        comboadd = QToolButton()
        comboadd.setIcon(get_icon('list-add'))
        comboadd.setToolTip('Add set')
        comboadd.clicked.connect(self.addSet)

        hbox = QHBoxLayout()
        hbox.addWidget(self.setscombo)
        hbox.addWidget(comboadd)

        vbox.addLayout(hbox)

        conditions = QLabel('&Conditions')
        vbox.addWidget(conditions)

        self.listbox = ListBox()
        conditions.setBuddy(self.listbox)
        listbuttons = ListButtons()

        listhbox = QHBoxLayout()
        listhbox.addWidget(self.listbox)
        listhbox.addLayout(listbuttons)
        vbox.addLayout(listhbox)

        label = QLabel('Retrieve values via: ')
        self.maintag = QComboBox()
        self.maintag.addItems(['artist', 'title', 'genre', 'album', 'year'])
        maintaghbox = QHBoxLayout()
        maintaghbox.addWidget(label)
        maintaghbox.addWidget(self.maintag)
        maintaghbox.addStretch()
        vbox.addLayout(maintaghbox)

        dispformat = QLabel('Display Format')
        vbox.addWidget(dispformat)
        self.texts = [QLineEdit(), QLineEdit()]
        t = ['Original', 'Duplicates']
        for i, text in enumerate(self.texts):
            label = QLabel(t[i])
            label.setBuddy(text)
            dispbox = QHBoxLayout()
            dispbox.addWidget(label)
            dispbox.addWidget(text)
            vbox.addLayout(dispbox)

        okcancel = OKCancel()
        vbox.addLayout(okcancel)
        okcancel.ok.connect(self.okClicked)
        okcancel.cancel.connect(self.cancelClicked)
        self.setLayout(vbox)

        self.fill(loadsets())
        listbuttons.connectToWidget(self)

    def addSet(self):
        def gettext():
            (text, ok) = QInputDialog.getText(self, 'puddletag', 'Enter a name'
                                                                 'for the set', QLineEdit.EchoMode.Normal)
            if ok:
                if self.setscombo.findText(text) > -1:
                    QMessageBox.information(self, 'puddletag', 'The name entered already exists.')
                    return gettext()
                return text

        text = gettext()
        if text:
            self.setscombo.addItem(text)
            self._sets.append([str(text), ['', ''], []])
            self.setscombo.setCurrentIndex(self.setscombo.count() - 1)

    def fill(self, sets):
        if not sets:
            return
        self._sets = sets
        self.setscombo.clear()
        self.setscombo.addItems([z[0] for z in sets])
        self.currentSet = sets[0]
        self.setscombo.setCurrentIndex(0)
        self.setscombo.currentIndexChanged.connect(self.changeSet)

    @property
    def currentSet(self):
        return self._sets[self.setscombo.currentIndex()]

    @currentSet.setter
    def currentSet(self, s):
        [text.setText(disp) for text, disp in zip(self.texts, s[1])]
        self.listbox.clear()
        [self.listbox.addItem(alg.pprint()) for alg in s[2]]
        index = self.maintag.findText(s[3])
        if index > -1:
            self.maintag.setCurrentIndex(index)
        else:
            self.maintag.addItem(s[3])
            self.maintag.setCurrentIndex(self.maintag.count() - 1)

    def changeSet(self, index):
        i = self._previndex
        prevset = {'setname': self._sets[i][0],
                   'disp': [str(text.text()) for text in self.texts],
                   'algs': self._sets[i][2],
                   'maintag': str(self.maintag.currentText())}
        self._sets[i][1] = prevset['disp']
        self._sets[i][2] = prevset['algs']
        self._sets[i][3] = prevset['maintag']
        saveset(**prevset)
        self.currentSet = self._sets[index]
        self._previndex = index

    def add(self):
        win = AlgWin(self)
        win.setModal(True)
        win.okClickedSignal.connect(self.addBuddy)
        win.show()

    def addBuddy(self, alg):
        self.listbox.addItem(alg.pprint())
        self.currentSet[2].append(alg)

    def edit(self):
        win = AlgWin(self, self.currentSet[2][self.listbox.currentRow()])
        win.setModal(True)
        win.okClickedSignal.connect(self.editBuddy)
        win.show()

    def editBuddy(self, alg):
        self.listbox.item(self.listbox.currentRow()).setText(alg.pprint())
        self._sets[self._previndex][2][self.listbox.currentRow()] = alg

    def moveUp(self):
        self.listbox.moveUp(self.currentSet[2])

    def moveDown(self):
        self.listbox.moveDown(self.currentSet[2])

    def remove(self):
        del (self.currentSet[2][self.listbox.currentRow()])
        self.listbox.takeItem(self.listbox.currentRow())

    def okClicked(self):
        i = self.setscombo.currentIndex()
        prevset = {'setname': self._sets[i][0],
                   'disp': [str(text.text()) for text in self.texts],
                   'algs': self._sets[i][2],
                   'maintag': str(self.maintag.currentText())}
        saveset(**prevset)
        self.close()
        self.setAvailable.emit(self.currentSet)

    def cancelClicked(self):
        self.close()


def load_window(parent):
    from ..libraries import quodlibetlib as quodlibet
    from ..constants import HOMEDIR
    lib = quodlibet.QuodLibet(os.path.join(HOMEDIR, '.quodlibet/songs'))
    from Levenshtein import ratio
    algos = [Algo(['artist', 'title'], 0.80, ratio), Algo(['artist', 'title'], 0.70, ratio)]
    qb = parent.addDock('Duplicates', DupeTree, RIGHTDOCK, connect=True)
    qb.loadDupes(lib, algos, ['%artist% - %title%', '%title%'])


def init(parent=None):
    action = QAction('Dupes in Lib', parent)
    # if not status['library']:
    # action.setEnabled(False)
    action.triggered.connect(lambda: load_window(parent))
    add_shortcuts('&Tools', [action])


if __name__ == "__main__":
    from ..libraries import quodlibetlib as quodlibet
    from ..constants import HOMEDIR

    lib = quodlibet.QuodLibet(os.path.join(HOMEDIR, '.quodlibet/songs'))
    from Levenshtein import ratio

    algos = [Algo(['artist', 'title'], 0.80, ratio), Algo(['artist', 'title'], 0.70, ratio)]
    app = QApplication(sys.argv)
    qb = DupeTree()
    qb.show()
    QApplication.processEvents()
    qb.loadDupes(lib, algos, ['%artist% - %title%', '%title%'])
    app.exec_()
