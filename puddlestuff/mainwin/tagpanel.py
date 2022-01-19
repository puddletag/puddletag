import os
import sip
import sys

from PyQt5.QtCore import QEvent, QThread, Qt, pyqtRemoveInputHook, pyqtSignal
from PyQt5.QtGui import QBrush
from PyQt5.QtWidgets import QApplication, QComboBox, QCompleter, QDialog, QGroupBox, QHBoxLayout, \
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ..audioinfo import INFOTAGS
from ..puddleobjects import ListButtons, PuddleConfig

pyqtRemoveInputHook()
from ..constants import LEFTDOCK, SELECTIONCHANGED, BLANK, KEEP, SEPARATOR
from functools import partial
from ..puddlesettings import SettingsError
from ..translations import translate
from ..constants import CONFIGDIR


def loadsettings(filepath=None):
    settings = PuddleConfig()
    if filepath:
        settings.filename = filepath
    else:
        settings.filename = os.path.join(CONFIGDIR, 'tagpanel')
    numrows = settings.get('panel', 'numrows', -1, True)
    if numrows > -1:
        sections = settings.sections()
        d = {}
        for row in range(numrows):
            section = str(row)
            tags = settings.get(section, 'tags', [''])
            titles = settings.get(section, 'titles', [''])
            d[row] = list(zip(titles, tags))
    else:
        titles = ['&Artist', '&Title', 'Al&bum', 'T&rack', '&Year', "&Genre", '&Comment']
        tags = ['artist', 'title', 'album', 'track', 'year', 'genre', 'comment']
        newtags = list(zip(titles, tags))
        d = {0: [newtags[0]], 1: [newtags[1]], 2: [newtags[2]],
             3: [newtags[3], newtags[4], newtags[5]],
             4: [newtags[6]]}
    return d


def savesettings(d, filepath=None):
    settings = PuddleConfig()
    if filepath:
        settings.filename = filepath
    else:
        settings.filename = os.path.join(settings.savedir, 'tagpanel')
    settings.set('panel', 'numrows', str(len(d)))
    for row, rowtags in d.items():
        settings.set(str(row), 'tags', [z[1] for z in rowtags])
        settings.set(str(row), 'titles', [z[0] for z in rowtags])


class Combo(QComboBox):

    def __init__(self, *args, **kwargs):
        super(Combo, self).__init__(*args, **kwargs)
        self._edited = False

        def k(text): self._edited = True

        self.editTextChanged.connect(k)

    def setEditText(self, text):
        self._edited = False
        super(Combo, self).setEditText(text)

    def focusOutEvent(self, event):
        if not self._edited:
            return super(Combo, self).focusOutEvent(event)
        curtext = self.currentText()
        index = self.findText(curtext,
                              Qt.MatchExactly | Qt.MatchFixedString | Qt.MatchCaseSensitive)
        if index == -1:
            index = self.findText(curtext, Qt.MatchExactly | Qt.MatchFixedString)
        if index > 1:
            if curtext == self.itemText(index):
                self.removeItem(index)
            self.insertItem(2, curtext)
        self._edited = False
        return super(Combo, self).focusOutEvent(event)


class Thread(QThread):
    update = pyqtSignal(object, name='update')

    def __init__(self, values, parent=None):
        self._values = values
        QThread.__init__(self, parent)

    def run(self):
        self.update.emit(self._values)


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

    onetomany = pyqtSignal(dict, name='onetomany')
    onetomanypreview = pyqtSignal(dict, name='onetomanypreview')
    manypreview = pyqtSignal(list, name='manypreview')

    def __init__(self, tags=None, parent=None, status=None):
        self.settingsdialog = SettingsWin
        QGroupBox.__init__(self, parent)
        self.emits = ['onetomany', 'onetomanypreview', 'manypreview']
        self.receives = [(SELECTIONCHANGED, self.fillCombos),
                         ('previewModeChanged', lambda v: self._enablePreview()
                         if v else self._disablePreview()), ]
        self.combos = {}
        self.labels = {}
        self._hboxes = []
        self._status = status
        self._originalValues = {}
        self.__indexFuncs = []

    def _disablePreview(self):
        self.__disconnectIndexChanged
        self.__indexFuncs = []
        for field, combo in self.combos.items():
            edit = QLineEdit()
            combo.setLineEdit(edit)
            completer = combo.completer()
            completer.setCaseSensitivity(Qt.CaseSensitive)
            completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)

    def disableCombos(self):
        for z in self.combos:
            self.combos[z].clear()
            self.combos[z].setEnabled(False)

    def _enablePreview(self):
        self.__indexFuncs = []
        for field, combo in self.combos.items():
            func = partial(self._emitChange, field)
            edit = QLineEdit()
            combo.setLineEdit(edit)
            completer = combo.completer()
            completer.setCaseSensitivity(Qt.CaseSensitive)
            completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
            edit.textEdited.connect(func)
            combo.currentIndexChanged.connect(func)
            self.__indexFuncs.append((combo, func))
            edit.editingFinished.connect(self.save)

    def __disconnectIndexChanged(self):
        for combo, func in self.__indexFuncs:
            combo.disconnect(combo, func)

    def _emitChange(self, field, text):
        if type(text) is int:
            text = self.combos[field].itemText(text)
        else:
            text = str(text)

        if text == BLANK:
            text = ''
        elif text == KEEP:
            if self._audios:
                self.manypreview.emit([{field: a.get(field, '')} for a in self._audios])
        else:
            if field in INFOTAGS:
                value = text
            else:
                value = text.split(SEPARATOR)
        self.onetomanypreview.emit({field: text})

    def fillCombos(self, *args):
        audios = self._status['selectedfiles']
        self._audios = [z.usertags for z in audios]
        combos = self.combos

        if not audios:
            for combo in combos.values():
                combo.clear()
                combo.setEnabled(False)
            return

        [combo.blockSignals(True) for combo in combos.values()]
        self.initCombos(True)
        tags = dict((tag, set()) for tag in combos)
        for audio in audios:
            for field in tags:
                if field in audio:
                    value = audio[field]
                    if isinstance(value, str):
                        tags[field].add(value)
                    else:
                        tags[field].add(SEPARATOR.join(value))
                else:
                    tags[field].add('')

        for field, values in tags.items():
            combo = combos[field]
            combo.addItems(sorted(values))
            if len(values) == 1:
                combo.setCurrentIndex(2)
            else:
                combo.setCurrentIndex(0)

        if 'genre' in tags and len(tags['genre']) == 1:
            combo = combos['genre']
            values = sorted(tags['genre'])
            index = combo.findText(values[0])
            if index > -1:
                combo.setCurrentIndex(index)
            else:
                combo.setEditText(values[0])
        elif 'genre' in tags:
            combos['genre'].setCurrentIndex(0)

        self._originalValues = dict([(field, str(combo.currentText()))
                                     for field, combo in self.combos.items()])
        self._originalValues['__image'] = self._status['images']
        [combo.blockSignals(False) for combo in combos.values()]

    def save(self):
        """Writes the tags of the selected files to the values in self.combogroup.combos."""
        combos = self.combos
        tags = {}

        images = self._status['images']
        if images is not None:
            tags['__image'] = images
        originals = {}
        for field, combo in combos.items():
            curtext = str(combo.currentText())
            if self._originalValues[field] == curtext:
                continue
            originals[field] = curtext
            if curtext == BLANK:
                tags[field] = []
            elif curtext == KEEP:
                continue
            else:
                if field in INFOTAGS:
                    tags[field] = curtext
                else:
                    tags[field] = curtext.split(SEPARATOR)

        if '__image' in tags:
            if self._originalValues['__image'] == tags['__image']:
                del (tags['__image'])
            else:
                originals['__image'] = tags['__image']

        if not tags:
            return

        self._originalValues.update(originals)
        self.onetomany.emit(tags)
        if 'genre' in combos:
            combo = combos['genre']

            genres = self._status['genres']
            new_genres = [_f for _f in str(combo.currentText()).split(SEPARATOR) if _f]

            [genres.append(genre) for genre in new_genres
             if genre not in genres]

    def setCombos(self, rowtags):
        """Creates a vertical column of comboboxes.
        tags are tags is usual in the (tag, backgroundvalue) case[should be enumerable].
        rows are a dictionary with each key being a list of the indexes of tags that should
        be one one row.

        E.g Say you wanted to have the artist, album, title, and comments on
        seperate rows. But then you want year, genre and track on one row. With that
        row being before the comments row. You'd do something like...

        >>>tags = [('Artist', 'artist'), ('Title', 'title'), ('Album', 'album'),
        ...        ('Track', 'track'), ("Comments",'comment'), ('Genre', 'genre'), ('Year', 'date')]
        >>>rows = {0:[0], 1:[1], 2:[2], 3[3,4,6],4:[5]
        >>>f = FrameCombo()
        >>>f.setCombo(tags, rows)"""
        # pdb.set_trace()

        if self.combos:
            vbox = self.layout()
            for box, control in self._hboxes:
                box.removeWidget(control)
                sip.delete(control)
                if not box.count():
                    vbox.removeItem(box)
                    sip.delete(box)
        else:
            vbox = QVBoxLayout()
            vbox.setContentsMargins(0, 0, 0, 0)
        self.combos = {}
        self.labels = {}
        self._hboxes = []

        j = 0
        for row, tags in sorted(rowtags.items()):
            labelbox = QHBoxLayout()
            labelbox.setContentsMargins(6, 1, 1, 1)
            widgetbox = QHBoxLayout()
            widgetbox.setContentsMargins(0, 0, 0, 0)
            for tag in tags:
                tagval = tag[1]
                self.labels[tagval] = QLabel(tag[0])
                self.combos[tagval] = QComboBox(self)
                self.combos[tagval].setInsertPolicy(QComboBox.NoInsert)
                self.combos[tagval].setEditable(True)
                self.combos[tagval].completer().setCompletionMode(
                    QCompleter.UnfilteredPopupCompletion)
                self.combos[tagval].completer().setCaseSensitivity(
                    Qt.CaseSensitive)
                self.labels[tagval].setBuddy(self.combos[tagval])
                labelbox.addWidget(self.labels[tagval])
                widgetbox.addWidget(self.combos[tagval])
                self._hboxes.append((labelbox, self.labels[tagval]))
                self._hboxes.append((widgetbox, self.combos[tagval]))
            vbox.addLayout(labelbox)
            vbox.addLayout(widgetbox)

        self.setLayout(vbox)
        QApplication.processEvents()
        self.setMaximumHeight(self.sizeHint().height())

    def eventFilter(self, obj, event):
        if isinstance(obj, QComboBox) and event.type() == QEvent.FocusOut:
            return False
        return QGroupBox.eventFilter(self, obj, event)

    def initCombos(self, enable=False):
        """Clears the comboboxes and adds two items, <keep> and <blank>.
        If <keep> is selected and the tags in the combos are saved,
        then they remain unchanged. If <blank> is selected, then the tag is removed"""
        for combo in self.combos.values():
            combo.clear()
            combo.setEnabled(enable)
            combo.addItems([KEEP, BLANK])

        if 'genre' in self.combos:
            pass
            self.combos['genre'].addItems(self._status['genres'])

    def reloadCombos(self, tags):
        self.setCombos(tags)

    def loadSettings(self):
        self.setCombos(loadsettings())


class PuddleTable(QTableWidget):
    def __init__(self, columns=None, defaultvals=None, parent=None):
        QTableWidget.__init__(self, parent)
        self._default = defaultvals
        self.verticalHeader().hide()
        if columns:
            self.setColumnCount(len(columns))
            self.setHorizontalHeaderLabels(columns)
            self.horizontalHeader().setStretchLastSection(True)

    def add(self, texts=None):
        row = self.rowCount()
        item = self.horizontalHeaderItem
        if self._default and (not texts):
            texts = self._default
        elif not texts:
            texts = [item(z).text() for z in range(self.columnCount())]
        self.insertRow(row)
        for column, v in enumerate(texts):
            self.setItem(row, column, QTableWidgetItem(v))

    def remove(self):
        rows = self.selectedRows()
        if not rows:
            return
        for i in range(len(rows)):
            self.removeRow(rows[i])
            rows = [z - 1 for z in rows]
        self.itemSelectionChanged.emit()

    def moveUp(self):
        row = self.currentRow()
        if row <= 0:
            return
        previtems = self.texts(row - 1)
        newitems = self.texts(row)
        self.setRowTexts(row, previtems)
        self.setRowTexts(row - 1, newitems)
        curitem = self.item(row - 1, self.currentItem().column())
        self.setCurrentItem(curitem)

    def moveDown(self):
        row = self.currentRow()
        if row >= self.rowCount() - 1:
            return
        previtems = self.texts(row + 1)
        newitems = self.texts(row)
        self.setRowTexts(row, previtems)
        self.setRowTexts(row + 1, newitems)
        curitem = self.item(row + 1, self.currentItem().column())
        self.setCurrentItem(curitem)

    rows = property(lambda x: range(x.rowCount()))

    def setRowTexts(self, row, texts):
        item = self.item
        for column, text in zip(list(range(self.columnCount())), texts):
            item(row, column).setText(text)

    def texts(self, row):
        item = self.item
        return [str(item(row, z).text()) for z in range(self.columnCount())]

    def items(self, row):
        item = self.item
        return [item(row, z) for z in range(self.columnCount())]

    def text(self, row, column):
        return str(self.item(row, column).text())

    def selectedRows(self):
        return sorted(set(i.row() for i in self.selectedIndexes()))


TABLEWIDGETBG = QTableWidgetItem().background()
RED = QBrush(Qt.red)

TITLE = translate("Defaults", 'Title')
FIELD = translate("Defaults", 'Field')
ROW = translate("Tag Panel Settings", 'Row')


class SettingsWin(QWidget):

    def __init__(self, parent=None, status=None):
        QDialog.__init__(self, parent)
        self.title = translate('Settings', 'Tag Panel')
        self._table = PuddleTable([TITLE, FIELD, ROW],
                                  [TITLE, FIELD, '0'], self)
        self._buttons = ListButtons()
        self._buttons.connectToWidget(self._table, add=self.add,
                                      edit=self.edit, moveup=self._table.moveUp,
                                      movedown=self._table.moveDown, duplicate=self.duplicate)

        hbox = QHBoxLayout()
        hbox.addWidget(self._table, 1)
        hbox.addLayout(self._buttons, 0)
        self.setLayout(hbox)

        self._table.cellChanged.connect(self._checkItem)
        self._table.itemSelectionChanged.connect(self._enableButtons)
        self.fill()

    def add(self, texts=None):
        table = self._table
        if not texts:
            text = table.text
            rows = []
            for row in table.rows:
                try:
                    rows.append(int(text(row, 2)))
                except (TypeError, ValueError):
                    pass
            row = str(max(rows) + 1) if rows else '1'
            table.add([TITLE, FIELD.lower(), row])
        else:
            table.add(texts)
        item = table.item(table.rowCount() - 1, 0)
        table.setCurrentItem(item)
        table.editItem(item)

    def fill(self):
        d = loadsettings()
        self._old = d
        for row in d:
            for z in d[row]:
                self._table.add(z + (str(row),))

    def applySettings(self, control=None):
        texts = self._table.texts
        d = {}
        for row in self._table.rows:
            l = texts(row)
            try:
                l[2] = int(l[2])
            except ValueError:
                raise SettingsError(translate('Tag Panel Settings',
                                              'All row numbers must be integers.'))
            try:
                d[l[2]].append(l[:-1])
            except KeyError:
                d[l[2]] = [l[:-1]]
        d = dict([(i, d[v]) for i, v in enumerate(sorted(d))])  # consecutive rows
        if self._old == d:
            return
        savesettings(d)
        control.setCombos(d)

    def edit(self):
        self._table.editItem(self._table.currentItem())

    def _checkItem(self, row, column):
        table = self._table
        if column == 2:
            try:
                int(table.text(row, column))
                table.item(row, column).setBackground(TABLEWIDGETBG)
            except ValueError:
                i = table.item(row, column)
                i.setBackground(RED)

    def _enableButtons(self):
        table = self._table
        if table.rowCount() <= 0:
            self._buttons.editButton.setEnabled(False)
            self._buttons.duplicateButton.setEnabled(False)
            self._buttons.removeButton.setEnabled(False)
        elif self._table.selectedRows():
            self._buttons.editButton.setEnabled(True)
            self._buttons.duplicateButton.setEnabled(True)
            self._buttons.removeButton.setEnabled(True)

    def duplicate(self):
        table = self._table
        row = table.currentRow()
        if row < 0: return
        self.add(table.texts(row))


control = ('Tag Panel', FrameCombo, LEFTDOCK, True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = SettingsWin()
    win.show()
    app.exec_()
