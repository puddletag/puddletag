import os
import re
import sys
import time
from copy import copy, deepcopy
from operator import itemgetter
from os import path
from subprocess import Popen

from PyQt5.QtCore import QAbstractTableModel, QEvent, QItemSelection, QItemSelectionModel, QItemSelectionRange, \
    QMimeData, QModelIndex, QPoint, QUrl, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QDrag, QPalette
from PyQt5.QtWidgets import QAbstractItemDelegate, QAction, QApplication, QDialog, QGridLayout, QGroupBox, \
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QStyledItemDelegate, QTableView, \
    QVBoxLayout

from . import audioinfo
from .audioinfo import (PATH, FILENAME, DIRPATH, FILETAGS, READONLY, INFOTAGS, DIRNAME,
                        EXTENSION, CaselessDict, encode_fn, decode_fn)
from .puddleobjects import (unique, partial, natural_sort_key, gettag,
                            HeaderSetting, getfiles, progress, PuddleConfig, singleerror, winsettings, issubfolder,
                            fnmatch)

from collections import defaultdict
from .util import write, to_string
from .constants import SELECTIONCHANGED, SEPARATOR, BLANK
from . import confirmations
import logging
from .translations import translate
from .util import rename_error_msg
from .audio_filter import parse as filter_audio

the_break = False

status = {}

LIBRARY = '__library'
HIGHLIGHTCOLOR = Qt.green
SHIFT_RETURN = 2
RETURN_ONLY = 1


def _default_audio_player():
    if sys.platform.startswith("linux"):
        return 'xdg-open'
    elif sys.platform == "darwin":
        return 'open -a iTunes'
    return "clementine -p"


def commontag(tag, tags):
    x = defaultdict(lambda: [])
    for audio in tags:
        if tag in audio:
            x[audio[tag][0]].append(audio)
        else:
            x[''].append(audio)
    return x


def not_in_dirs(files, dirs):
    if not dirs:
        return files
    for d in dirs:
        d = encode_fn(d)
        return [z for z in files if not z.startswith(d)]


def loadsettings(filepath=None):
    settings = PuddleConfig()
    if filepath:
        settings.filename = filepath
    titles = settings.get('tableheader', 'titles', [
        translate('Fields', 'Filename'), translate('Fields', 'Artist'),
        translate('Fields', 'Title'), translate('Fields', 'Album'),
        translate('Fields', 'Track'), translate('Fields', 'Length'),
        translate('Fields', 'Year'), translate('Fields', 'Bitrate'),
        translate('Fields', 'Genre'), translate('Fields', 'Comment'),
        translate('Fields', 'Dirpath')])
    tags = settings.get('tableheader', 'tags',
                        ['__filename', 'artist', 'title', 'album', 'track',
                         '__length', 'year', '__bitrate', 'genre', 'comment', '__dirpath'])
    # checked = settings.get('tableheader', 'enabled', range(len(tags)), True)
    # checked = []
    fontsize = settings.get('table', 'fontsize', 0, True)
    rowsize = settings.get('table', 'rowsize', -1, True)
    v1_option = settings.get('id3tags', 'v1_option', 2)
    v2_option = settings.get('id3tags', 'v2_option', 4)
    audioinfo.id3.v1_option = v1_option
    audioinfo.id3.v2_option = v2_option
    filespec = ';'.join(settings.get('table', 'filespec', []))

    return (list(zip(titles, tags)), fontsize, rowsize, filespec)


def caseless(tag, audio):
    if tag in audio:
        return tag
    smalltag = tag.lower()
    try:
        return [z for z in audio if isinstance(z, str) and z.lower() == smalltag][0]
    except IndexError:
        return tag


def has_previews(tags=None, parent=None, msg=None):
    """Disables preview mode. Returns True if disable successful, else False.

    Displays a confirmation to the user (message box) asking if they want
    to exit Preview Mode if any files contain previews. If the user selects
    that they want to exit, then True is returned. Preview Mode is not
    changed.

    If not previews in tags, then True is returned.

    tags is a list of audioinfo.Tag object with the preview attribute.
        If preview not empty, the file will be considered to have a preview.
        If not specified status['alltags'] is used.
    parent => A window to have as the parent for the message box.
    msg => Message to show in message box.
    """

    if msg is None:
        msg = translate("Previews", 'Do you want to exit Preview Mode?')

    if tags is None:
        tags = status['alltags']

    previews = False
    for z in tags:
        if z.preview:
            previews = True
            break

    if previews and confirmations.should_show('preview_mode'):
        ret = QMessageBox.question(parent, 'puddletag', msg)
        if ret != QMessageBox.Yes:
            return True
    return False


def tag_in_file(tag, audio):
    if tag in audio:
        return tag
    smalltag = tag.lower()
    try:
        return [z for z in audio if z.lower() == smalltag][0]
    except IndexError:
        return None


def model_tag(model, base=audioinfo.AbstractTag):
    class ModelTag(base):
        def __init__(self, *args, **kwargs):
            self.preview = CaselessDict()
            self.edited = None
            super(ModelTag, self).__init__(*args, **kwargs)

        def _get_images(self):
            if not self.IMAGETAGS:
                return []
            if model.previewMode and '__image' in self.preview:
                return self.preview['__image']
            else:
                return base.images.fget(self)

        def _set_images(self, value):
            if not self.IMAGETAGS:
                return
            if model.previewMode:
                self.preview['__image'] = value
            else:
                base.images.fset(self, value)

        images = property(_get_images, _set_images)

        def __contains__(self, key):
            if model.previewMode:
                if key in self.preview:
                    return True
            return base.__contains__(self, key)

        def clear(self):
            self.preview.clear()
            super(ModelTag, self).clear()

        def clean(self):
            for k, v in self.preview.items():
                real = self.realvalue(k, '')
                if not isinstance(real, str):
                    real = ''.join(real)

                if not isinstance(v, str):
                    v = ''.join(v)

                if real == v:
                    del (self.preview[k])

        def __delitem__(self, key):
            if key in INFOTAGS:
                return
            if model.previewMode and key in self.preview:
                del (self.preview[key])
            else:
                super(ModelTag, self).__delitem__(key)

        def delete(self, tag=None):
            if model.previewMode:
                return
            try:
                base.delete(self, tag)
            except TypeError:
                base.delete(self)

        def equal_fields(self):
            if not (model.previewMode and self.preview):
                return []
            ret = []
            for k, v in self.preview.items():
                if k == '__image':
                    continue
                real = self.realvalue(k, '')
                if not isinstance(real, str):
                    real = ''.join(real)

                if not isinstance(v, str):
                    v = ''.join(v)

                if real == v:
                    ret.append(k)
            return ret

        def __getitem__(self, key):
            if model.previewMode and key in self.preview:
                return self.preview[key]
            else:
                return super(ModelTag, self).__getitem__(key)

        def keys(self):
            keys = list(super(ModelTag, self).keys())
            if model.previewMode and self.preview:
                [keys.append(key) for key in self.preview
                 if key not in keys]
            return keys

        def __len__(self):
            return len(list(self.keys()))

        def realvalue(self, key, default=None):
            try:
                return base.__getitem__(self, key)
            except KeyError:
                if default is not None:
                    return default
                raise

        def __setitem__(self, key, value):
            if model.previewMode:
                if key in FILETAGS:
                    value = to_string(value)

                if key not in READONLY:
                    if not value and key in self.preview:
                        del (self.preview[key])
                        return
                    self.preview[key] = value
            else:
                super(ModelTag, self).__setitem__(key, value)

        def remove_from_preview(self, key):
            if key == EXTENSION:
                del (self.preview[key])
            elif key == FILENAME:
                for k in [FILENAME, EXTENSION, PATH]:
                    if k in self.preview:
                        del (self.preview[k])
            elif key in FILETAGS:
                for k in FILETAGS:
                    if k in self.preview:
                        del (self.preview[k])
            else:
                del (self.preview[key])

        def update(self, *args, **kwargs):
            if model.previewMode:
                self.preview.update(*args, **kwargs)
            else:
                super(ModelTag, self).update(*args, **kwargs)

    return ModelTag


def _Tag(model):
    splitext = path.splitext
    extensions = audioinfo.extensions

    options = [[Kind[0], model_tag(model, Kind[1]), Kind[2]] for Kind
               in audioinfo.options]
    filetypes = dict([(z[0], z) for z in options])

    extension_regex = re.compile('\.(%s)$' % '|'.join(extensions))

    def ReplacementTag(filename):

        try:
            fileobj = open(filename, "rb")
        except IOError:
            logging.info("Can't open file %s", filename)
            return None

        match = extension_regex.search(filename)
        if match:
            return filetypes[extensions[match.groups()[0]][0]][1](filename)

        try:
            header = fileobj.read(128)
            results = [Kind[0].score(filename, fileobj, header) for Kind in options]
        finally:
            fileobj.close()
        results = list(zip(results, options))
        results.sort(key=lambda x: x[0])
        score, Kind = results[-1]

        if score > 0:
            return Kind[1](filename)
        else:
            return None

    return ReplacementTag


class Properties(QDialog):
    def __init__(self, info, parent=None):
        """Shows a window with the properties in info.

        info should be a list of 2-entry tuples. These tuples should consists
        of a string in the 0-th index to be used as the title of a group.
        The first index (the properties) should also be a list length 2 tuples.
        Both indexes containing strings. Where the 0-th is used as the description
        and the other as the value.

        .e.g
        [('File', [('Filename', '/Hip Hop Songs/Nas-These Are Our Heroes .mp3'),
                  ('Size', '6151 kB'),
                  ('Path', 'Nas - These Are Our Heroes .mp3'),
                  ('Modified', '2009-07-28 14:04:05'),
                  ('ID3 Version', 'ID3v2.4')]),
        ('Version', [('Version', 'MPEG 1 Layer 3'),
                    ('Bitrate', '192 kb/s'),
                    ('Frequency', '44.1 kHz'),
                    ('Mode', 'Stereo'),
                    ('Length', '4:22')])]
        """
        QDialog.__init__(self, parent)
        winsettings('fileinfo', self)
        self.setWindowTitle(translate("Shortcut Settings", 'File Properties'))
        self._load(info)

    def _load(self, info):
        vbox = QVBoxLayout()
        interaction = Qt.TextSelectableByMouse or Qt.TextSelectableByKeyboard
        for title, items in info:
            frame = QGroupBox(title)
            framegrid = QGridLayout()
            framegrid.setColumnStretch(1, 1)
            for row, value in enumerate(items):
                prop = QLabel(value[0] + ':')
                prop.setTextInteractionFlags(interaction)
                framegrid.addWidget(prop, row, 0)
                propvalue = QLabel('<b>%s</b>' % value[1])

                propvalue.setTextInteractionFlags(interaction)
                framegrid.addWidget(propvalue, row, 1)
            frame.setLayout(framegrid)
            vbox.addWidget(frame)
        close = QPushButton('Close')
        close.clicked.connect(self.close)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(close)
        vbox.addLayout(hbox)
        self.setLayout(vbox)


class ColumnSettings(HeaderSetting):
    """A dialog that allows you to edit the header of a TagTable widget."""
    title = translate("Column Settings", 'Columns')

    def __init__(self, parent=None, showok=False, status=None, table=None):

        self.tags, fontsize, rowsize, filespec = loadsettings()

        checked = []

        if table is None and status is not None:
            table = status['table']

        if table is not None:
            tags = table.model().headerdata
            hd = table.horizontalHeader()

            tags = ([hd.visualIndex(i), z, hd.isSectionHidden(i)] for i, z in
                    enumerate(tags))
            tags = sorted(tags)
            checked = [i for i, t in enumerate(tags) if not t[2]]
            tags = [tuple(z[1]) for z in tags]
            [tags.append(z) for z in self.tags if z not in tags]
            self.tags = tags

        HeaderSetting.__init__(self, self.tags, parent, showok, True)

        if showok:
            winsettings('columnsettings', self)

        self.setWindowFlags(Qt.Widget)
        label = QLabel(translate("Column Settings", 'Adjust visibility of columns.'))
        self.grid.addWidget(label, 0, 0)
        items = [self.listbox.item(z) for z in range(self.listbox.count())]

        if not checked:
            checked = list(range(len(tags)))
        [z.setCheckState(Qt.Checked) if i in checked
         else z.setCheckState(Qt.Unchecked) for i, z in enumerate(items)]

    def applySettings(self, control=None):
        row = self.listbox.currentRow()
        if row > -1:
            self.tags[row][0] = str(self.textname.text())
            self.tags[row][1] = str(self.tag.currentText())
        checked = [z for z in range(self.listbox.count()) if
                   self.listbox.item(z).checkState()]
        titles = [z[0] for z in self.tags]
        tags = [z[1] for z in self.tags]
        cparser = PuddleConfig()
        cparser.set('tableheader', 'titles', titles)
        cparser.set('tableheader', 'tags', tags)

        hidden = [i for i, z in enumerate(self.tags) if i not in checked]

        if control:
            control.horizontalHeader().reset()
            control.setHeaderTags(self.tags, hidden)
            control.restoreSelection()
            control.horizontalHeader().reset()
        else:
            self.headerChanged.emit(self.tags, hidden)

    def add(self):
        HeaderSetting.add(self)
        self.listbox.currentItem().setCheckState(True)

    def duplicate(self):
        item = self.listbox.currentItem()
        if item:
            checked = item.checkState()
        HeaderSetting.duplicate(self)
        self.listbox.currentItem().setCheckState(checked)

    def okClicked(self):
        self.applySettings()
        self.close()


class TagModel(QAbstractTableModel):
    """The model used in TableShit
    Methods you shoud take not of are(read docstrings for more):

    setData -> As per the usual model, can only write one tag at a time.
    setRowData -> Writes a row's tags at once.
    undo -> undo's changes
    setTestData and unSetTestData -> Used to display temporary values in the table.
    """
    fileChanged = pyqtSignal(name='fileChanged')
    aboutToSort = pyqtSignal(name='aboutToSort')
    sorted = pyqtSignal(name='sorted')
    previewModeChanged = pyqtSignal(bool, name='previewModeChanged')
    dirsmoved = pyqtSignal(list, name='dirsmoved')
    libfilesedited = pyqtSignal(list, name='libfilesedited')
    setDataError = pyqtSignal(str, name='setDataError')
    enableUndo = pyqtSignal(bool, name='enableUndo')

    def __init__(self, headerdata, taginfo=None):
        """Load tags.

        headerdata must be a list of tuples
        where the first item is the displayrole and the second
        the tag to be used as in [("Artist", "artist"), ("Title", title")].

        taginfo is a list of audioinfo.Tag objects."""

        QAbstractTableModel.__init__(self)
        self.alternateAlbumColors = True
        self._headerData = []
        self.headerdata = headerdata
        self.colorRows = []
        self.sortOrder = (0, Qt.AscendingOrder)
        self.saveModification = True
        self._filtered = []
        self._previewMode = False
        self._prevhighlight = []
        self._permah = []
        self.permaColor = QColor(Qt.green)
        self._colored = []
        audioinfo.Tag = _Tag(self)
        audioinfo.model_tag = partial(model_tag, self)
        self.showToolTip = True
        status['previewmode'] = False
        self._previewBackground = None
        self._selectionBackground = None
        self._undo = defaultdict(lambda: {})
        self._previewUndo = defaultdict(lambda: {})
        self.sortFields = []
        self.reverseSort = True
        self._savedundolevel = None

        if taginfo is not None:
            self.taginfo = unique(taginfo)
            self.sortByFields(self.sortFields, reverse=self.reverseSort)
        else:
            self.taginfo = []
            self.reset()
        for z in self.taginfo:
            z.preview = {}
            z.previewundo = {}
            z.undo = {}
            z.color = None
            z._temp = {}
            if not hasattr(z, 'library'):
                z.library = None
        self.undolevel = 0
        self._fontSize = QFont().pointSize()

    def _setFontSize(self, size):
        self._fontSize = size
        top = self.index(self.rowCount(), 0)
        bottom = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(top, bottom)

    def _getFontSize(self):
        return self._fontSize

    fontSize = property(_getFontSize, _setFontSize)

    def _getHeaderData(self):
        return self._headerData

    def _setHeaderData(self, tags):

        new_tags = []
        indexes = {}

        for i, t in enumerate(tags):
            t = tuple(t)
            if t not in indexes:
                indexes[t] = i
                new_tags.append(t)

        self._headerData = new_tags

        self.columns = dict((field, i) for i, (title, field) in
                            enumerate(new_tags))

    headerdata = property(_getHeaderData, _setHeaderData)

    def _get_pBg(self):
        return self._previewBackground

    def _set_pBg(self, val):
        self._previewBackground = val
        rows = [i for i, z in enumerate(self.taginfo) if z.preview]
        if rows:
            top = self.index(min(rows), 0)
            bottom = self.index(max(rows), self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)

    previewBackground = property(_get_pBg, _set_pBg)

    def _get_previewMode(self):
        return self._previewMode

    def _set_previewMode(self, value):
        if not value and self._previewMode:
            rows = []
            for row, audio in enumerate(self.taginfo):
                if audio.preview:
                    audio.preview = {}
                    rows.append(row)
            if rows:
                top = self.index(min(rows), 0)
                bottom = self.index(max(rows), self.columnCount() - 1)
                self.dataChanged.emit(top, bottom)

            self.undolevel = self._savedundolevel
            self._previewUndo.clear()
        else:
            self._savedundolevel = self.undolevel
        self._previewMode = value
        status['previewmode'] = value
        self.previewModeChanged.emit(value)

    previewMode = property(_get_previewMode, _set_previewMode)

    def _get_sBg(self):
        return self._selectionBackground

    def _set_sBg(self, val):
        self._selectionBackground = val
        rows = [i for i, z in enumerate(self.taginfo) if z.color]
        if rows:
            top = self.index(min(rows), 0)
            bottom = self.index(max(rows), self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)

    selectionBackground = property(_get_sBg, _set_sBg)

    def _getUndoLevel(self):
        return self._undolevel

    def _setUndoLevel(self, value):
        if value == 0:
            self.enableUndo.emit(False)
            if self.previewMode:
                self._previewUndo.clear()
            else:
                self._undo.clear()
        else:
            self.enableUndo.emit(True)
        self._undolevel = value

    undolevel = property(_getUndoLevel, _setUndoLevel)

    def _addUndo(self, audio, undo):
        if self.previewMode:
            self._previewUndo[self.undolevel][audio] = undo
        else:
            self._undo[self.undolevel][audio] = undo

    def applyFilter(self, pattern=None, matchcase=True):
        self.taginfo = self.taginfo + self._filtered
        taginfo = self.taginfo
        if (not pattern) and (not self._filtered):
            return
        elif not pattern:
            self._filtered = []
            self.reset()
            return

        filtered = [(filter_audio(a, pattern), a) for a in self.taginfo]
        self._filtered = [z[1] for z in filtered if not z[0]]
        self.taginfo = [z[1] for z in filtered if z[0]]
        self.reset()

    def changeFolder(self, olddir, newdir):
        """Used for changing the directory of all the files in olddir to newdir.
        i.e. All children of olddir will now become children of newdir

        No actual moving is done though."""

        olddir = encode_fn(olddir)

        folder = itemgetter(DIRPATH)
        tags = [(i, z) for i, z in enumerate(self.taginfo)
                if z.dirpath.startswith(olddir)]
        libtags = []
        for i, audio in tags:
            if audio.dirpath == olddir:
                audio.dirpath = newdir
            elif issubfolder(olddir, audio.dirpath):  # Newdir is a parent
                audio.dirpath = os.path.join(newdir, audio.dirname)
            if audio.library:
                audio.save(True)
        rows = [z[0] for z in tags]
        if rows:
            self.dataChanged.emit(
                self.index(min(rows), 0), self.index(max(rows),
                                                     self.columnCount() - 1))

    def columnCount(self, index=QModelIndex()):
        return len(self.headerdata)

    def _toString(self, val):
        if isinstance(val, str):
            return val.replace('\n', ' ')
        else:
            try:
                return '\\\\'.join(val).replace('\n', ' ')
            except TypeError:
                return str(val)

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if not index.isValid() or not (0 <= row < len(self.taginfo)):
            return None

        if role in (Qt.DisplayRole, Qt.ToolTipRole, Qt.EditRole):
            try:
                audio = self.taginfo[row]
                tag = self.headerdata[index.column()][1]
                val = self._toString(audio[tag])
            except (KeyError, IndexError):
                return None

            if role == Qt.ToolTipRole:
                if not self.showToolTip:
                    return None
                if self.previewMode and \
                        audio.preview and tag in audio.preview:
                    try:
                        real = self._toString(audio.realvalue(tag))
                        if not real:
                            real = BLANK
                    except KeyError:
                        real = BLANK
                    if real != val:
                        tooltip = str(translate("Table", 'Preview: %1\nReal: %2').arg(val).arg(self._toString(real)))
                    else:
                        tooltip = val
                else:
                    tooltip = val
                return tooltip
            return val
        elif role == Qt.BackgroundColorRole:
            audio = self.taginfo[row]
            if audio.color:
                return audio.color
            elif self.previewMode and audio.preview:
                return self.previewBackground
        elif role == Qt.FontRole:

            field = self.headerdata[index.column()][1]
            f = QFont()
            if f.pointSize() != self.fontSize:
                f.setPointSize(self.fontSize)
            audio = self.taginfo[row]
            if field in audio.preview:
                real = audio.realvalue(field, '')
                if self._toString(audio[field]) != self._toString(real):
                    f.setBold(True)
                else:
                    f.setItalic(True)
            return f
        return None

    def deleteTag(self, row=None, audio=None, delete=True):
        if row is not None:
            audio = self.taginfo[row]
        tags = audio.usertags
        try:
            tags['__image'] = audio['__image']
        except KeyError:
            pass
        if delete:
            audio.delete()
        self._addUndo(audio, tags)

    def deleteTags(self, rows):
        [self.deleteTag(row) for row in rows]
        self.undolevel += 1

    def dropMimeData(self, data, action, row, column, parent=QModelIndex()):
        return True

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index) |
                            Qt.ItemIsEditable | Qt.ItemIsDropEnabled)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return int(Qt.AlignLeft | Qt.AlignVCenter)
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return str(self.headerdata[section][0])
            except IndexError:
                return None
        return int(section + 1)

    def highlight(self, rows):
        rows = rows[::]
        hcolor = self.selectionBackground
        nolight = set(self._prevhighlight).difference(rows)
        self._prevhighlight = rows[::]
        rows.extend(nolight)
        taginfo = self.taginfo

        def set_color(row):
            if row < len(taginfo):
                if row in nolight:
                    if taginfo[row] in self._colored:
                        taginfo[row].color = self.permaColor
                    else:
                        taginfo[row].color = None
                else:
                    taginfo[row].color = hcolor

        [set_color(row) for row in rows]
        if rows:
            top = self.index(min(rows), 0)
            bottom = self.index(max(rows), self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)

    def insertColumns(self, column, count, parent=QModelIndex(), data=None):
        self.beginInsertColumns(parent, column, column + count)
        if data:
            self.headerdata.extend(data)
        else:
            self.headerdata += [("", "") for z in range(count - column + 1)]
        self.endInsertColumns()
        # self.modelReset.emit() #Because of the strange behaviour mentioned in reset.
        return True

    def reloadTags(self, tags):
        for z in tags:
            z.preview = {}
            z.undo = {}
            z.previewundo = {}
            z.color = None
            z._temp = {}
            if not hasattr(z, 'library'):
                z.library = None

        fns = dict((f.filepath, i) for i, f in enumerate(self.taginfo))

        to_append = []

        num_rows_to_insert = 0

        first = self.rowCount()
        for t in tags:
            if t.filepath in fns:
                self.taginfo[fns[t.filepath]] = t
            else:
                self.taginfo.append(t)
                num_rows_to_insert = 1

        self.beginInsertRows(QModelIndex(), first, len(self.taginfo) - 1)
        self.endInsertRows()

    def load(self, taginfo, headerdata=None, append=False):
        """Loads tags as in __init__.
        If append is true, then the tags are just appended."""
        if headerdata is not None:
            self.headerdata = headerdata

        for z in taginfo:
            z.preview = {}
            z.undo = {}
            z.previewundo = {}
            z.color = None
            z._temp = {}
            if not hasattr(z, 'library'):
                z.library = None

        if append:
            for field in self.sortFields:
                getter = lambda audio: audio.get(field, '')
                taginfo.sort(key=lambda a: natural_sort_key(a.get(field, '')), reverse=self.reverseSort)

            filenames = [z.filepath for z in self.taginfo]
            self.taginfo.extend([z for z in taginfo if z.filepath
                                 not in filenames])

            first = self.rowCount()
            self.beginInsertRows(QModelIndex(), first, first + len(taginfo) - 1)
            self.endInsertRows()

            top = self.index(first, 0)
            bottom = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)
        else:
            top = self.index(0, 0)
            self.taginfo = taginfo
            self._filtered = []
            self.reset()
            self.sortByFields(self.sortFields, reverse=self.reverseSort)
            [setattr(z, 'color', None) for z in self.taginfo if z.color]
            self.undolevel = 0

    def moveRows(self, rows, row):

        taginfo = self.taginfo
        rows = sorted(rows)

        tags = [taginfo[i] for i in rows]

        num_moved = len(rows)

        first = min(rows)
        first = first if first < row else row

        last = max(rows)
        last = last if last > row else row

        top = self.index(first, 0)
        bottom = self.index(last, self.columnCount() - 1)

        while rows:
            del (taginfo[rows[0]])
            rows = [i - 1 for i in rows[1:]]

        if row >= len(taginfo):
            row = row - num_moved
            taginfo.extend(tags)

        [taginfo.insert(row, z) for z in reversed(tags)]

        self.dataChanged.emit(top, bottom)

    def permaHighlight(self, rows):
        rows = rows[::]
        hcolor = self.permaColor
        nolight = set(self._permah).difference(rows)
        self._permah = rows[::]
        rows.extend(nolight)
        taginfo = self.taginfo

        def set_color(row):
            if row < len(taginfo):
                if row in nolight:
                    taginfo[row].color = None
                else:
                    taginfo[row].color = hcolor

        [set_color(row) for row in rows]
        if rows:
            top = self.index(min(rows), 0)
            bottom = self.index(max(rows), self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)

    def setColors(self, tags):
        for f in self._colored:
            f.color = None
        for tag in tags:
            tag.color = self.permaColor
        index = self.taginfo.index

        def row_index(tag):
            try:
                return index(tag)
            except ValueError:
                return len(self.taginfo)

        rows = list(map(row_index, tags + self._colored))
        if rows:
            top = self.index(min(rows), 0)
            bottom = self.index(max(rows), self.columnCount() - 1)
            self.dataChanged.emit(top, bottom)
        self._colored = tags

    def removeColumns(self, column, count, parent=QModelIndex()):
        self.beginRemoveColumns(QModelIndex(), column, column + count - 1)
        del (self.headerdata[column: column + count])
        self.endRemoveColumns()
        return True

    def removeFolders(self, folders, v=True):
        if v:
            f = [i for i, tag in enumerate(self.taginfo) if tag.dirpath
                 not in folders and not tag.library]
        else:
            f = [i for i, tag in enumerate(self.taginfo) if tag.dirpath
                 in folders and not tag.library]
        while f:
            try:
                self.removeRows(f[0])
                del (f[0])
                f = [z - 1 for z in f]
            except IndexError:
                break

    def removeRows(self, position, rows=1, index=QModelIndex()):
        """Please, only use this function to remove one row at a time. For some reason, it doesn't work
        too well on debian if more than one row is removed at a time."""
        self.beginRemoveRows(QModelIndex(), position,
                             position + rows - 1)
        del (self.taginfo[position])
        self.endRemoveRows()
        return True

    def reset(self):
        # Sometimes, (actually all the time on my box, but it may be different on yours)
        # if a number files loaded into the model is equal to number
        # of files currently in the model then the TableView isn't updated.
        # Why the fuck I don't know, but this signal, intercepted by the table,
        # updates the view and makes everything work okay.
        self.beginResetModel()
        self.modelReset.emit()
        self.endResetModel()

    def rowColors(self, rows=None, clear=False):
        """Changes the background of rows to green.

        If rows is None, then the background of all the rows in the table
        are returned to normal."""
        taginfo = self.taginfo
        if rows:
            if clear:
                for row in rows:
                    if hasattr(taginfo[row], "color"):
                        del (taginfo[row].color)
            else:
                for row in rows:
                    taginfo[row].color = HIGHLIGHTCOLOR
                for i, z in enumerate(taginfo):
                    if i not in rows and hasattr(taginfo[row], "color"):
                        del (taginfo[row].color)
        else:
            rows = []
            for i, tag in enumerate(self.taginfo):
                if hasattr(tag, 'color'):
                    del (tag.color)
                    rows.append(i)
        if rows:
            firstindex = self.index(min(rows), 0)
            lastindex = self.index(max(rows), self.columnCount() - 1)
            self.dataChanged.emit(firstindex, lastindex)

    def rowCount(self, index=QModelIndex()):
        return len(self.taginfo)

    def setData(self, index, value, role=Qt.EditRole, dontwrite=False):
        """Sets the data of the currently edited cell as expected.
        Also writes tags and increases the undolevel."""
        QApplication.setOverrideCursor(Qt.WaitCursor);
        if index.isValid() and 0 <= index.row() < len(self.taginfo):
            column = index.column()
            tag = self.headerdata[column][1]
            currentfile = self.taginfo[index.row()]
            newvalue = str(value)
            realtag = currentfile.mapping.get(tag, tag)
            if realtag in FILETAGS and tag not in [FILENAME, EXTENSION, DIRNAME]:
                QApplication.restoreOverrideCursor()
                return False

            if tag not in FILETAGS:
                newvalue = [_f for _f in newvalue.split(SEPARATOR) if _f]
            if newvalue == currentfile.get(tag, '') and not dontwrite:
                QApplication.restoreOverrideCursor()
                return False
            if dontwrite:
                QApplication.restoreOverrideCursor()
                return {tag: newvalue}, index.row()
            ret = self.setRowData(index.row(), {tag: newvalue}, undo=True)
            if not self.previewMode and currentfile.library:
                self.libfilesedited.emit([ret])
            self.undolevel += 1
            self.fileChanged.emit()
            QApplication.restoreOverrideCursor()
            return True
        return False

    def setHeaderData(self, section, orientation, value, role=Qt.EditRole):
        if (orientation == Qt.Horizontal) and (role == Qt.DisplayRole):
            self.headerdata[section] = value

        self.headerdata = self.headerdata  # make sure columns are set

        self.headerDataChanged.emit(orientation, section, section)

    def setHeader(self, tags):
        self.headerdata = tags
        self.headerDataChanged.emit(
            Qt.Horizontal, 0, len(self.headerdata))
        self.reset()

    def setRowData(self, row, tags, undo=False, justrename=False, temp=False):
        """A function to update one row.
        row is the row, tags is a dictionary of tags.

        If undo`is True, then an undo level is created for this file.
        If justrename is True, then (if tags contain a PATH or EXTENSION key)
        the file is just renamed i.e not tags are written.
        """
        audio = self.taginfo[row]

        temporary = temp
        ret = None
        oldpath = audio.dirpath

        if self.previewMode:
            if temporary:
                for field in tags:
                    if field not in audio._temp:
                        audio._temp[field] = audio.get(field, '')
            preview = audio.preview
            undo_val = dict([(tag, copy(audio[tag])) if tag in audio
                             else (tag, []) for tag in tags])
            audio.update(tags)
            if undo:
                if audio._temp:
                    undo_val.update(audio._temp)
                    audio._temp = {}
                self._addUndo(audio, undo_val)
            return
        else:
            artist = audio.get('artist', '')
            try:
                undo_val = write(audio, tags, self.saveModification, justrename)
            except PermissionError as e:
                raise e
            if undo and undo_val:
                self._addUndo(audio, undo_val)

            if DIRNAME in tags or DIRPATH in tags:
                self.changeFolder(oldpath, audio.dirpath)
                self.dirsmoved.emit([[oldpath, audio.dirpath]])
            if justrename and audio.library:
                audio.save(True)
            ret = (artist, tags)

        return ret

    def setTestData(self, rows, previews=None):
        """A method that allows you to change the visible data of
        the model without writing tags.

        rows is the rows that you want to change
        previews -> is the tags that are to be shown."""
        taginfo = self.taginfo
        if rows and (not previews):
            index = taginfo.index
            tags = rows
            previews = []
            rows = []
            for audio, preview in tags.items():
                rows.append(index(audio))
                previews.append(preview)
        if not rows:
            return
        if not self.previewMode:
            return
        unsetrows = rows[len(previews):]

        if unsetrows:
            self.unSetTestData(rows=unsetrows)
        for row, preview in zip(rows, previews):
            taginfo[row].preview.clear()
            taginfo[row].update(preview)
        firstindex = self.index(min(rows), 0)
        lastindex = self.index(max(rows), self.columnCount() - 1)
        self.dataChanged.emit(firstindex, lastindex)
        self.fileChanged.emit()

    def sibling(self, row, column, index=QModelIndex()):
        if row < (self.rowCount()) and row >= 0:
            return self.index(row, column)
        return QModelIndex();

    def sort(self, column, order=Qt.DescendingOrder):
        try:
            field = self.headerdata[column][1]
        except IndexError:
            if len(self.headerdata) >= 1:
                field = self.headerdata[0][1]
            else:
                return
        if order == Qt.DescendingOrder:
            self.sortByFields([field], reverse=True)
        else:
            self.sortByFields([field], reverse=False)

    def sortByFields(self, fields, files=None, rows=None, reverse=None):

        self.aboutToSort.emit()

        if reverse is None and fields == self.sortFields:
            reverse = not self.reverseSort
        elif reverse is None:
            reverse = False

        if files and rows:
            for field in fields:
                files.sort(key=lambda a: natural_sort_key(a.get(field, '')), reverse=reverse)
            for index, row in enumerate(rows):
                self.taginfo[row] = files[index]
        else:
            for field in fields:
                self.taginfo.sort(key=lambda a: natural_sort_key(a.get(field, '')), reverse=reverse)

        self.reverseSort = reverse
        self.sortFields = fields
        self.reset()
        self.sorted.emit()

    def supportedDropActions(self):
        return Qt.CopyAction

    def undo(self):
        """Undos the last action.

        Basically, if a tag has a key which is = self.undolevel - 1,
        then the tag is updated with the dictionary in that key.

        setRowData does not modify the undoleve unless you explicitely tell
        it, but setData does modify the undolevel.

        It is recommended that you use consecutive indexes for self.undolevel."""
        if self.undolevel <= 0:
            self.undolevel = 0
            return
        level = self.undolevel - 1
        oldfiles = []
        newfiles = []
        rows = []
        edited = []
        if self.previewMode:
            undo = self._previewUndo
        else:
            undo = self._undo
        if level not in undo:
            return

        get_row = self.taginfo.index

        for audio, undo_tags in undo[level].items():
            row = get_row(audio)
            rows.append(row)
            if self.previewMode:
                audio.update(undo_tags)
                for k, v in undo_tags.items():
                    if v == [] and k in audio.preview:
                        del (audio.preview[k])
            else:
                if audio.library:
                    oldfiles.append(deepcopy(audio.tags))
                edited.append(self.setRowData(row, undo_tags, False))

        del (undo[level])
        if rows:
            self.updateTable(rows)
            if edited:
                self.libfilesedited.emit(edited)
        if self.undolevel > 0:
            self.undolevel -= 1

    def unSetTestData(self, rows=None):
        taginfo = self.taginfo
        if not rows:
            rows = [i for i, z in enumerate(taginfo) if z.preview]
            if not rows:
                return
        for row in rows:
            taginfo[row].preview = {}

        if rows:
            firstindex = self.index(min(rows), 0)
            lastindex = self.index(max(rows), self.columnCount() - 1)
            self.dataChanged.emit(firstindex, lastindex)

    def updateTable(self, rows):
        firstindex = self.index(min(rows), 0)
        lastindex = self.index(max(rows), self.columnCount() - 1)
        self.dataChanged.emit(firstindex, lastindex)


class TagDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        # logging.debug('Creating editor')
        editor = QLineEdit(parent)
        editor.returnPressed = False
        editor.writeError = False
        editor.setFrame(False)
        font = editor.font()
        font.setPointSize(index.model().fontSize)
        editor.setFont(font)

        # logging.debug('Closing editor.')
        return editor

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.key() == Qt.Key_Return:
                    shift_pressed = event.modifiers() == Qt.ShiftModifier
                else:
                    shift_pressed = event.modifiers() == Qt.ShiftModifier | Qt.KeypadModifier
                if shift_pressed:
                    editor.returnPressed = SHIFT_RETURN
                else:
                    editor.returnPressed = RETURN_ONLY
        return QStyledItemDelegate.eventFilter(self, editor, event)

    def setModelData(self, editor, model, index):
        try:
            model.setData(index, editor.text())
        except EnvironmentError as e:
            editor.writeError = e


class TableHeader(QHeaderView):
    """A headerview put here simply to enable the contextMenuEvent
    so that I can show the edit columns menu.

    Call it with tags in the usual form, to set the top header."""
    saveSelection = pyqtSignal(name='saveSelection')
    headerChanged = pyqtSignal([list, list], name='headerChanged')

    def __init__(self, orientation, tags=None, parent=None):
        QHeaderView.__init__(self, orientation, parent)
        if tags is not None: self.tags = tags
        self.setSectionsClickable(True)
        self.setHighlightSections(True)
        self.setSectionsMovable(True)
        self.setSortIndicatorShown(True)
        self.setSortIndicator(0, Qt.AscendingOrder)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        settings = menu.addAction(
            translate("Column Settings", "&Select Columns"))
        settings.triggered.connect(self.setTitles)

        menu.exec_(event.globalPos())

    def mousePressEvent(self, event):
        if event.button == Qt.RightButton:
            self.contextMenuEvent(event)
            return
        QHeaderView.mousePressEvent(self, event)

    def setTitles(self):
        self.win = ColumnSettings(showok=True, table=self.parent())
        self.win.setModal(True)
        self.win.show()
        self.win.headerChanged.connect(self.headerChanged)


class VerticalHeader(QHeaderView):
    def __init__(self, orientation, parent=None):
        QHeaderView.__init__(self, orientation, parent)
        self.setDefaultSectionSize(self.minimumSectionSize() + 3)
        self.setMinimumSectionSize(1)

        self.sectionResized.connect(self._resize)

    def _resize(self, row, oldsize, newsize):
        self.setDefaultSectionSize(newsize)


class TagTable(QTableView):
    """I need a more descriptive name for this.

    This table is the table that handles all my tags for me.
    The main functions and properties are:

    rowTags(row) -> Returns the tags from a row.
    updateRow(row, tags) - > Updates a row with the tags specified
    selectedRows -> A list of currently selected rows
    remRows() -> Removes the selected rows.
    playcommand -> Command to run to play files.
    """
    dirschanged = pyqtSignal(list, name='dirschanged')
    tagselectionchanged = pyqtSignal(name='tagselectionchanged')
    filesloaded = pyqtSignal(bool, name='filesloaded')
    viewfilled = pyqtSignal(bool, name='viewfilled')
    filesselected = pyqtSignal(bool, name='filesselected')
    enableUndo = pyqtSignal(bool, name='enableUndo')
    playlistchanged = pyqtSignal(str, name='playlistchanged')
    deletedfromlib = pyqtSignal(list, name='deletedfromlib')
    libfilesedited = pyqtSignal(list, name='libfilesedited')
    previewModeChanged = pyqtSignal(bool, name='previewModeChanged')
    onetomany = pyqtSignal(dict, name='onetomany')
    setDataError = pyqtSignal(str, name='setDataError')
    dirsmoved = pyqtSignal(list, name='dirsmoved')
    itemSelectionChanged = pyqtSignal(name='itemSelectionChanged')

    def __init__(self, headerdata=None, parent=None):
        QTableView.__init__(self, parent)
        self.setSelectionMode(self.ExtendedSelection)
        self.settingsdialog = ColumnSettings
        if not headerdata:
            headerdata = []
        header = TableHeader(Qt.Horizontal, headerdata, self)
        header.setSortIndicatorShown(True)
        self.setSortingEnabled(True)
        self._savedSelection = False

        self.setVerticalHeader(VerticalHeader(Qt.Vertical))
        self.setHorizontalHeader(header)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.showmsg = True
        self._currentcol = {}
        self._currentrow = {}
        self._currenttags = []
        self.dirs = []
        self._resize = False
        self._restore = False
        self._selectedRows = []
        self._selectedColumns = []
        self._select = True
        self._playlist = False
        self.filespec = ''
        self.contextMenu = None
        self.setHorizontalScrollMode(self.ScrollPerPixel)

        model = TagModel(headerdata)
        header.headerChanged.connect(self.setHeaderTags)
        self.setModel(model)

        def emitundo(val):
            self.enableUndo.emit(val)
            self.selectionChanged()

        model.enableUndo.connect(emitundo)
        model.libfilesedited.connect(self.libfilesedited)
        self.undo = model.undo

        self.closeEditor = self._closeEditor
        delegate = TagDelegate(self)
        self.setItemDelegate(delegate)

        self.subFolders = False

        def sep():
            separator = QAction(self)
            separator.setSeparator(True)
            return separator

        self.emits = ['dirschanged', SELECTIONCHANGED, 'filesloaded',
                      'viewfilled', 'filesselected', 'enableUndo',
                      'playlistchanged', 'deletedfromlib', 'libfilesedited',
                      'previewModeChanged', 'onetomany']
        self.receives = [
            ('loadFiles', self.loadFiles),
            ('removeFolders', self.removeFolders),
            ('filter', self.applyFilter),
            ('setpreview', self.setTestData),
            ('loadtags', self.load_tags),
            ('highlight', self.highlight),
            ('enable_preview_mode', partial(self.previewMode, True)),
            ('disable_preview_mode', partial(self.previewMode, False)),
        ]

        self.gensettings = [
            ('Su&bfolders', True),
            ('Show &gridlines', True),
            ('Show tooltips in file-view:', True),
            ('Show &row numbers', True),
            ('Automatically resize columns to contents', False),
            ('&Preserve file modification times (if supported)', False),
            ('Program to &play files with:', _default_audio_player())
        ]

        status['selectedrows'] = self._getSelectedRows
        status['selectedfiles'] = self._selectedTags
        status['firstselection'] = self._firstSelection
        status['selectedcolumns'] = self._getSelectedColumns
        status['selectedtags'] = self._getSelectedTags
        status['alltags'] = lambda: self.model().taginfo
        status['allfiles'] = lambda: self.model().taginfo
        status['table'] = self

    def _setFontSize(self, size):
        self.model().fontSize = size

    def _getFontSize(self):
        return self.model().fontSize

    fontSize = property(_getFontSize, _setFontSize)

    def increaseFont(self):
        self.fontSize += 1

    def decreaseFont(self):
        self.fontSize -= 1

    def _getResize(self):
        return self._resize

    def _setResize(self, value):
        self._resize = value
        if value:
            self.resizeColumnsToContents()
            self.model().modelReset.connect(self.resizeColumnsToContents)
        else:
            try:
                self.model().modelReset.disconnect(self.resizeColumnsToContents)
            except TypeError:
                logging.debug("Tried to disconnect un-connected Resize-Slot")

    def _getSelectedTags(self):
        columns = dict([(v, k) for k, v in self.model().columns.items()])
        rows = self.currentRowSelection()
        audios = self.selectedTags

        def get_selected(f, row):
            selected = (columns[column] for column in rows[row])

            return ((field, f.get(field, '')) for field in selected)

        return list(map(dict, (get_selected(*z) for z in zip(audios, sorted(rows)))))

    def _firstSelection(self):
        if not self.selectedRows:
            raise IndexError

        get_index = self.model().index
        isselected = self.selectionModel().isSelected

        field_mapping = dict([(v, k) for k, v in self.model().columns.items()])
        row = min(self.selectedRows)
        fields = [field_mapping[c] for c in range(self.columnCount())
                  if isselected(get_index(row, c))]

        audio = self.model().taginfo[row]

        return audio, dict((field, audio.get(field, '')) for field in fields)

    def applyGenSettings(self, d, startlevel=None):
        self.saveSelection()
        if not startlevel:
            self.subFolders = d['Su&bfolders']
            self.setShowGrid(d['Show &gridlines'])
            self.verticalHeader().setVisible(d['Show &row numbers'])
            self.autoresize = d['Automatically resize columns to contents']
            self.model().saveModification = d[
                '&Preserve file modification times (if supported)']
            self.playcommand = d['Program to &play files with:'].split(' ')
            self.model().showToolTip = d['Show tooltips in file-view:']

    def applyFilter(self, pattern=None, matchcase=True):
        self.saveSelection()
        self.clearSelection()
        self.model().applyFilter(pattern, matchcase)
        self.restoreSelection()

    autoresize = property(_getResize, _setResize)

    def changeFolder(self, olddir, newdir, updatemodel=True):
        try:
            for i, d in enumerate(self.dirs[::]):
                if d == olddir:
                    self.dirs[i] = newdir
                elif d.startswith(olddir):
                    self.dirs[i] = newdir + d[len(olddir):]
        except IndexError:
            pass
        if updatemodel:
            self.model().changeFolder(olddir, newdir)

    def clearAll(self):
        self.model().taginfo = []
        self.model().reset()
        self.dirschanged.emit([])

    def _closeEditor(self, editor, hint=QAbstractItemDelegate.NoHint):
        if editor.writeError:
            model = self.model()
            currentfile = model.taginfo[self.currentIndex().row()]
            QTableView.closeEditor(self, editor, QAbstractItemDelegate.NoHint)
            model.setDataError.emit(
                rename_error_msg(editor.writeError, currentfile.filepath))
            return

        if len(self.selectedRows) > 1:
            QTableView.closeEditor(self, editor, QAbstractItemDelegate.NoHint)
        elif not editor.returnPressed:
            QTableView.closeEditor(self, editor, hint)
        else:
            index = self.currentIndex()
            newindex = None

            if editor.returnPressed == RETURN_ONLY:
                if index.row() < self.rowCount() - 1:
                    newindex = self.model().index(index.row() + 1,
                                                  index.column())
            elif editor.returnPressed == SHIFT_RETURN:
                if index.row() > 0:
                    newindex = self.model().index(index.row() - 1,
                                                  index.column())

            if newindex:
                QTableView.closeEditor(self, editor, QAbstractItemDelegate.NoHint)
                self.setCurrentIndex(newindex)
                self.edit(newindex)
            else:
                QTableView.closeEditor(self, editor, QAbstractItemDelegate.NoHint)

    def removeTags(self):
        if self.model().previewMode:
            QMessageBox.information(self, 'puddletag',
                                    translate("Table", 'Disable Preview Mode first to enable tag deletion.'))
            return
        deltag = self.model().deleteTag

        def func():
            for row in self.selectedRows:
                try:
                    deltag(row)
                    yield None
                except (OSError, IOError) as e:
                    msg = translate('Table', "An error occurred while " \
                                             "deleting the tag of %1: <b>%2</b>")
                    msg = msg.arg(e.filename).arg(e.strerror)
                    yield msg, len(self.selectedRows)
                except NotImplementedError as e:
                    f = self.model().taginfo[row]
                    filename = f[PATH]
                    ext = f[EXTENSION]
                    rowlen = len(self.selectedRows)
                    yield translate("Table", "There was an error deleting the "
                                             "tag of %1: <b>Tag deletion isn't supported"
                                             "for %2 files.</b>").arg(filename).arg(ext), rowlen

        def fin():
            self.selectionChanged()
            self.model().undolevel += 1

        f = progress(func, translate("Table", 'Deleting tag... '),
                     len(self.selectedRows), fin)
        f(self)

    def columnCount(self):
        return self.model().columnCount()

    def rowCount(self):
        return self.model().rowCount()

    def contextMenuEvent(self, event):
        if self.contextMenu:
            self.contextMenu.exec_(event.globalPos())

    def _isEmpty(self):
        if self.model().rowCount() <= 0:
            return True
        return False

    isempty = property(_isEmpty)

    def deleteSelectedWithoutMessage(self):
        self.deleteSelected(showmsg=False)

    def deleteSelected(self, delfiles=True, ifgone=False, showmsg=None):
        if showmsg is None:
            showmsg = True
            showmsg = confirmations.should_show('delete_files')

        if delfiles and showmsg:
            result = QMessageBox.question(self, "puddletag",
                                          translate("Table", "Are you sure you want to delete the selected files?"))
        else:
            result = QMessageBox.Yes
        if result != QMessageBox.Yes:
            return
        selected = self.selectedTags
        selectedRows = self.selectedRows
        removeRows = self.model().removeRows
        curindex = self.currentIndex()
        last = max(selectedRows) - len(selectedRows) + 1, curindex.column()
        libtags = []

        def func():
            temprows = sorted(selectedRows[::])
            for ((i, row), audio) in zip(enumerate(selectedRows), selected):
                try:
                    filename = audio.filepath
                    os.remove(filename)
                    if audio.library:
                        audio.remove()
                        libtags.append(audio)
                    removeRows(temprows[i])
                    temprows = [z - 1 for z in temprows]
                    yield None
                except (OSError, IOError) as detail:
                    msg = "I couldn't delete <b>%s</b> (%s)" % (filename,
                                                                detail.strerror)
                    if row == temprows[-1]:
                        yield msg, 1
                    else:
                        yield msg, len(selectedRows)

        def fin():
            index = self.model().index(*last)
            if libtags:
                self.deletedfromlib.emit(libtags)
            if index.isValid():
                self.setCurrentIndex(index)
            else:
                self.selectionChanged()

        s = progress(func, translate("Table", 'Deleting '), len(selectedRows), fin)
        if self.parentWidget():
            s(self.parentWidget())
        else:
            s(self)

    def dragEnterEvent(self, event):
        event.accept()
        event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        if event.source() == self and \
                hasattr(mime, 'draggedRows') and mime.draggedRows:

            row = self.rowAt(event.pos().y())
            if row == -1:
                row = self.rowCount() - 1
            self.saveSelection()
            self.model().moveRows(mime.draggedRows, row)
            self.restoreSelection()
        else:
            filenames = [z.path() for z
                         in event.mimeData().urls()]

            dirs = []
            files = []

            for f in filenames:
                if not f:
                    continue
                if os.path.isdir(f):
                    dirs.append(f)
                else:
                    files.append(f)

            self.loadFiles(files, dirs, append=True)

    def dragMoveEvent(self, event):
        mime = event.mimeData()
        if event.source() == self:
            if hasattr(mime, 'draggedRows') and mime.draggedRows:
                event.accept()
            else:
                event.ignore()
            return

        if mime.hasUrls():
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):

        if event.buttons() != Qt.LeftButton:
            return
        mimeData = QMimeData()
        plainText = ""
        tags = []
        if hasattr(self, "selectedRows"):
            selectedRows = self.selectedRows[::]
        else:
            return
        try:
            pnt = QPoint(*self.StartPosition)
        except AttributeError:
            return
        if (event.pos() - pnt).manhattanLength() < QApplication.startDragDistance():
            return
        filenames = [z.filepath for z in self.selectedTags]
        urls = list(map(QUrl.fromLocalFile, list(map(decode_fn, filenames))))
        mimeData = QMimeData()
        mimeData.setUrls(urls)
        if event.modifiers() == Qt.MetaModifier:
            mimeData.draggedRows = self.selectedRows[::]
        else:
            mimeData.draggedRows = None

        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.setHotSpot(event.pos() - self.rect().topLeft())
        dropaction = drag.exec_()
        if dropaction == Qt.MoveAction:
            if not os.path.exists(filenames[0]):
                self.deleteSelected(False, False, False)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.StartPosition = [event.pos().x(), event.pos().y()]
        QTableView.mousePressEvent(self, event)

    def fillTable(self, tags, append=False):
        """Clears the table and fills it with metadata in tags.

        tags are a list of audioinfo.Tag objects.
        If append is True then the tags are just appended.
        """
        self.selectedRows = []
        self.selectedColumns = []
        if append is None:
            self.model().reloadTags(tags)
        else:
            self.model().load(tags, append=append)

        QApplication.processEvents()
        if append or append is None:
            self.restoreSelection()
        else:
            self.selectCorner()

        if self.autoresize:
            self.resizeColumnsToContents()
        if self.model().taginfo:
            self.viewfilled.emit(True)
        else:
            self.viewfilled.emit(False)

    def highlight(self, rows):
        self.model().setColors(rows)

    def invertSelection(self):
        model = self.model()
        topLeft = model.index(0, 0)
        bottomRight = model.index(model.rowCount() - 1, model.columnCount() - 1)

        selection = QItemSelection(topLeft, bottomRight)
        self.selectionModel().select(selection, QItemSelectionModel.Toggle)

    def keyPressEvent(self, event):
        event.accept()
        # You might think that this is redundant since a delete
        # action is defined in contextMenuEvent, but if this isn't
        # done then the delegate is entered.

        has_modifier = event.modifiers() in [Qt.ControlModifier, Qt.ShiftModifier, Qt.ControlModifier | Qt.ShiftModifier]
        if event.key() == Qt.Key_Delete and self.selectedRows:
            self.deleteSelected()
            return
        # This is so that an item isn't edited when the user's holding the shift or
        # control key.
        elif event.key() == Qt.Key_Space and (has_modifier):
            trigger = self.editTriggers()
            self.setEditTriggers(self.NoEditTriggers)
            ret = QTableView.keyPressEvent(self, event)
            self.setEditTriggers(trigger)
            return ret
        return QTableView.keyPressEvent(self, event)

    def loadFiles(self, files=None, dirs=None, append=False, subfolders=None,
                  filepath=None, post_process=None):
        assert files or dirs, 'Either files or dirs (or both) must be specified.'

        if subfolders is None:
            subfolders = self.subFolders

        if not files:
            files = []
        if not dirs:
            dirs = []
        elif isinstance(dirs, str):
            dirs = [dirs]

        dirs = list(map(encode_fn, dirs))

        files = not_in_dirs(not_in_dirs(files, dirs), self.dirs)

        if subfolders:
            new_dirs = []
            for i, d in enumerate(dirs):
                if not [z for z in dirs if issubfolder(z, d, None)]:
                    new_dirs.append(d)

            dirs = new_dirs

        if append:
            self.saveSelection()
            if subfolders:
                # Remove all subfolders if the parent's already loaded.
                for d in self.dirs:
                    dirs = [z for z in dirs if not z.startswith(d)]
                toremove = set()
                for d in dirs:
                    toremove = toremove.union([z for z in self.dirs if z.startswith(d)])
                self.removeFolders(toremove)
            else:
                self.removeFolders([z for z in dirs if z in self.dirs], False)
            self.dirs.extend(dirs)
        else:
            self.dirs = dirs

        if not files and not dirs:
            return

        tags = []
        if len(dirs) == 1:
            reading_dir = translate("Defaults",
                                    'Reading Directory: %1').arg(dirs[0])
        elif dirs:
            reading_dir = translate("Defaults",
                                    'Reading Directory: %1 + others').arg(dirs[0])
        else:
            reading_dir = translate('Defaults', 'Reading Dir')

        def load_dir():
            if files:
                filenames = files
            else:
                filenames = []
            for fname in getfiles(dirs, subfolders):
                filenames.append(fname)
                yield reading_dir

            if self.filespec and self.filespec.strip():
                filenames = fnmatch(self.filespec, filenames)

            yield len(filenames)

            for fname in filenames:
                tag = gettag(fname)
                if tag is not None:
                    tags.append(tag)
                yield None

        if post_process:
            s = progress(load_dir, translate("Defaults", 'Loading '), 20,
                         lambda: post_process(tags, append, filepath))
        else:
            s = progress(load_dir, translate("Defaults", 'Loading '), 20,
                         lambda: self._loadFilesDone(tags, append, filepath))
        s(self.parentWidget())

    def _loadFilesDone(self, tags, append, filepath):
        self.fillTable(tags, append)
        if not filepath:
            self.dirschanged.emit(self.dirs[::])
        else:
            self.playlistchanged.emit(filepath)
            self.dirschanged.emit([])
        self.filesloaded.emit(True)
        if self._restore:
            self.restoreSelection(self._restore)

        model = self.model()
        start_index = model.index(0, 0)
        end_index = model.index(model.rowCount() - 1, model.columnCount() - 1)
        model.dataChanged.emit(start_index, end_index)
        # model.reset()
        self.selectionChanged()

    def load_tags(self, tags):
        self.fillTable(tags, False)
        self.dirs = []
        self.dirschanged.emit(self.dirs[::])
        self.filesloaded.emit(True)
        sortcolumn = self.horizontalHeader().sortIndicatorSection()
        QTableView.sortByColumn(self, sortcolumn)

    def loadSettings(self):
        (tags, fontsize, rowsize, self.filespec) = loadsettings()
        self.setHeaderTags(tags)
        if fontsize:
            self.fontSize = fontsize
        if rowsize > -1:
            self.verticalHeader().setDefaultSectionSize(rowsize)

        cparser = PuddleConfig()
        preview_color = cparser.get('table', 'preview_color', [192, 255, 192], True)
        default = QPalette().color(QPalette.Mid).getRgb()[:-1]
        selection_color = cparser.get('table', 'selected_color', default, True)

        model = self.model()

        model.previewBackground = QColor.fromRgb(*preview_color)
        model.selectionBackground = QColor.fromRgb(*selection_color)

        sort_fields = cparser.get('table', 'sort_fields', [])
        reverse = cparser.get('table', 'sort_reverse', False, True)

        # print sort_fields, model.sortFields

        if sort_fields:
            model.sortByFields(sort_fields, reverse=reverse)
        else:
            h = self.horizontalHeader()
            model.sort(h.sortIndicatorSection(), h.sortIndicatorOrder())

    def moveDown(self, rows=None):
        if rows is None:
            rows = self.selectedRows[::]
        if not rows:
            return
        elif max(rows) >= self.rowCount() - 1:
            return

        taginfo = self.model().taginfo

        self.saveSelection()
        self._select = False

        for row in reversed(rows):
            if row >= self.rowCount() - 1:
                continue
            old = taginfo[row]
            new = taginfo[row + 1]
            taginfo[row + 1] = old
            taginfo[row] = new

        getindex = self.model().index
        self.model().dataChanged.emit(getindex(min(rows), 0), getindex(max(rows), self.columnCount()))

        self.restoreSelection()
        self._select = True

    def moveUp(self, rows=None):
        if rows is None:
            rows = self.selectedRows[::]

        if not rows:
            return
        elif min(rows) <= 0:
            return

        taginfo = self.model().taginfo

        self.saveSelection()
        self._select = False

        for i, row in enumerate(rows):
            if row <= 0:
                continue
            old = taginfo[row]
            new = taginfo[row - 1]
            taginfo[row] = new
            taginfo[row - 1] = old

        getindex = self.model().index
        self.model().dataChanged.emit(getindex(min(rows), 0), getindex(max(rows), self.columnCount()))

        self.restoreSelection()
        self._select = True

    def playFiles(self):
        """Play the selected files using the player specified in self.playcommand"""
        if not self.selectedRows: return
        if hasattr(self, "playcommand"):

            li = list(map(encode_fn, self.playcommand))

            li.extend([z.filepath for z in self.selectedTags])

            try:
                Popen(li)
            except (OSError) as detail:
                if detail.errno != 2:
                    QMessageBox.critical(self, translate("Defaults", "Error"),
                                         translate("Table",
                                                   "An error occurred while trying to play the selected files: <b>%1</b> "
                                                   "<br />Does the music player you defined (<b>%2</b>)"
                                                   " exist?").arg(detail.strerror).arg(" ".join(self.playcommand)))
                else:
                    QMessageBox.critical(self, translate("Defaults", "Error"),
                                         translate("Table", "It wasn't possible to play the selected files, because the music player you defined (<b>%1</b>) does not exist.").arg(
                                             " ".join(self.playcommand)))

    def previewMode(self, value):
        if not value:
            if has_previews(self.model().taginfo, self):
                return False
        self.model().previewMode = value
        return value

    def reloadSelected(self, files=None):
        self._restore = self.saveSelection()

        loaded_dirs = list(map(encode_fn, self.dirs))
        if files is None:
            files = self.model().taginfo

        taginfo = self.model().taginfo
        dirs = set([taginfo[i].dirpath for i in self.selectedRows])

        is_sub = lambda fn: [_f for _f in [issubfolder(z, fn) for z in dirs] if _f]

        sub_files = []
        for f in files:
            if f.dirpath in dirs or is_sub(f.dirpath):
                sub_files.append(f)

        self.loadFiles(None, dirs, False, self.subFolders,
                       self._playlist,
                       lambda t, a, f: self.__processReload(t, a, f, sub_files))

    def __processReload(self, tags, append, filepath, sub_files):
        new_fns = set(z.filepath for z in tags)
        to_remove = set(z for z in sub_files
                        if z.filepath not in new_fns)
        self.model().taginfo = [z for z in self.model().taginfo if
                                z not in to_remove]
        self.fillTable(tags, None)
        model = self.model().reset()
        self.filesloaded.emit(True)
        if self._restore:
            self.restoreSelection(self._restore)

        self.selectionChanged()

    def reloadFiles(self, files=None):
        previews = False
        for z in self.model().taginfo:
            if z.preview:
                previews = True
                break
        if previews:
            ret = QMessageBox.question(self, 'puddletag',
                translate("Previews", 'There are unsaved changes pending. Do you want to discard and reload?'))
            if ret != QMessageBox.Yes:
                return

        self._restore = self.saveSelection()
        dirs = list(map(encode_fn, self.dirs))
        files = [z.filepath for z in self.model().taginfo if z.dirpath
                 not in dirs]
        libfiles = [z for z in self.model().taginfo if '__library' in z]
        if self._playlist:
            self.loadFiles(files, dirs, False, self.subFolders)
        else:
            self.loadFiles(files, dirs, False, self.subFolders,
                           self._playlist)
        self.model().load(libfiles, append=True)

    def rowTags(self, row, stringtags=False):
        """Returns all the tags pertinent to the file at row."""
        if stringtags:
            return self.model().taginfo[row].stringtags()
        return self.model().taginfo[row]

    def selectCurrentColumn(self):
        if self.selectedIndexes():
            col = self.currentIndex().column()
            model = self.model()
            topLeft = model.index(0, col)
            bottomRight = model.index(model.rowCount() - 1, col)

            selection = QItemSelection(topLeft, bottomRight)
            self.selectionModel().select(selection, QItemSelectionModel.Select)

    def selectCorner(self):
        topLeft = self.model().index(0, 0)
        selection = QItemSelection(topLeft, topLeft)
        self.selectionModel().select(selection, QItemSelectionModel.Select)
        self.setCurrentIndex(topLeft)

    def setModel(self, model):
        QTableView.setModel(self, model)
        self.updateRow = model.setRowData
        model.modelReset.connect(self.selectionChanged)
        model.setDataError.connect(self.writeError)
        model.fileChanged.connect(self.selectionChanged)
        model.aboutToSort.connect(self.saveBeforeReset)
        model.sorted.connect(self.restoreSort)
        model.previewModeChanged.connect(self.previewModeChanged)
        model.dirsmoved.connect(self.dirsmoved)
        set_data = model.setData

        def modded_setData(index, value, role=Qt.EditRole):
            if len(self.selectedRows) == 1:
                return set_data(index, value, role)
            ret = set_data(index, value, role, True)

            if ret:
                self.onetomany.emit(ret[0])
            return False

        model.setData = modded_setData

    def currentRowSelection(self):
        """Returns a dictionary with the currently selected rows as keys.
        Each key contains a list with the selected columns of that row.

        {} is returned if nothing is selected."""
        x = {}
        for z in self.selectedIndexes():
            try:
                x[z.row()].append(z.column())
            except KeyError:
                x[z.row()] = [z.column()]
        return x

    def currentColumnSelection(self):
        x = {}
        for z in self.selectedIndexes():
            try:
                x[z.column()].append(z.row())
            except KeyError:
                x[z.column()] = [z.row()]
        return x

    def _selectedTags(self):
        rowTags = self.rowTags
        return [rowTags(row) for row in self.selectedRows]

    selectedTags = property(_selectedTags)

    def _getSelectedRows(self):
        return self._selectedRows

    def _setSelectedRows(self, val):
        self._selectedRows = val

    selectedRows = property(_getSelectedRows, _setSelectedRows)

    def _getSelectedColumns(self):
        return self._selectedColumns

    def _setSelectedColumns(self, val):
        self._selectedColumns = val

    selectedColumns = property(_getSelectedColumns, _setSelectedColumns)

    def selectionChanged(self, selected=None, deselected=None):
        """Pretty important. This updates self.selectedRows, which is used
        everywhere.

        I've set selected an deselected as None, because I sometimes
        want self.selectedRows updated without hassle."""
        t = time.time()
        if selected is not None and deselected is not None:
            QTableView.selectionChanged(self, selected, deselected)
        taginfo = self.model().taginfo
        model = self.model()

        selectedRows = set()
        selectedColumns = set()

        for z in self.selectedIndexes():
            selectedRows.add(z.row())
            selectedColumns.add(z.column())
        self.selectedRows = sorted(list(selectedRows))
        self.selectedColumns = sorted(list(selectedColumns))

        if self._select:
            self.itemSelectionChanged.emit()
            if self.selectedRows:
                self.filesselected.emit(True)
            else:
                self.filesselected.emit(False)
            model.highlight(self.selectedRows)
            self.tagselectionchanged.emit()

    def saveBeforeReset(self):
        self.setCursor(Qt.BusyCursor)
        self._savedSelection = self.saveSelection()

    def restoreSort(self):
        self.setCursor(Qt.ArrowCursor)
        if self._savedSelection:
            self.restoreSelection(self._savedSelection)
            self._savedSelection = None
            return

    def saveSelection(self):
        taginfo = self.model().taginfo
        fields = [field for title, field in self.model().headerdata]
        filenames = defaultdict(lambda: set())
        selection = self.currentRowSelection()
        for row, columns in self.currentRowSelection().items():
            filenames[taginfo[row].filepath] = set(fields[c] for c in columns)
        self.__savedSelection = filenames
        return filenames

    def restoreReloadSelection(self, currentrow, currentcol, tags):
        if not tags:
            return

        def getGroups(rows):
            groups = []
            try:
                last = [rows[0]]
            except IndexError:
                return []
            for row in rows[1:]:
                if row - 1 == last[-1]:
                    last.append(row)
                else:
                    groups.append(last)
                    last = [row]
            groups.append(last)
            return groups

        modelindex = self.model().index
        filenames = [z.filepath for z in self.model().taginfo]
        getrow = lambda x: filenames.index(x.filepath)
        selection = QItemSelection()
        select = lambda top, low, col: selection.append(
            QItemSelectionRange(modelindex(top, col),
                                modelindex(low, col)))

        newindexes = {}
        while True:
            try:
                tag = tags[0]
            except IndexError:
                break
            try:
                newindexes[tag[0]] = getrow(tag[1])
            except ValueError:
                pass
            del (tags[0])

        groups = {}
        for col, rows in currentcol.items():
            groups[col] = getGroups(sorted([newindexes[row] for row in rows if row in newindexes]))

        for col, rows in groups.items():
            [select(min(row), max(row), col) for row in rows]
        self.selectionModel().select(selection, QItemSelectionModel.Select)

    def restoreSelection(self, data=None):
        if data is None:
            data = self.__savedSelection

        get_index = self.model().index
        selection = QItemSelection()

        def select_index(row, col):
            model_index = get_index(row, col)
            selection.select(model_index, model_index)

        columns = dict((field[1], i) for i, field in
                       enumerate(self.model().headerdata))

        for row, fn in enumerate(z.filepath for z in self.model().taginfo):
            selected_fields = data.get(fn)
            if not selected_fields:
                continue

            for field in selected_fields:
                column = columns.get(field)
                if column is not None:
                    select_index(row, column)

        self.selectionModel().clear()
        self.selectionModel().select(selection, QItemSelectionModel.SelectCurrent)
        self.model().highlight(self.selectedRows)

    def removeFolders(self, dirs, valid=True):
        if dirs:
            self.dirs = list(set(self.dirs).difference(dirs))
            self.model().removeFolders(dirs, valid)

    def setHeaderTags(self, tags, hidden=None):

        self.saveSelection()
        hd = TableHeader(Qt.Horizontal, tags, self)
        hd.setSortIndicatorShown(True)
        hd.setVisible(True)
        hd.headerChanged.connect(self.setHeaderTags)
        self.setHorizontalHeader(hd)
        self.model().setHeader(tags)

        if hidden is not None:
            for c in hidden:
                hd.hideSection(c)

        self.restoreSelection()

    def setHorizontalHeader(self, header):
        QTableView.setHorizontalHeader(self, header)
        header.saveSelection.connect(self.saveSelection)

    def writeError(self, text):
        """Shows a tooltip when an error occors.

        Actually, a tooltip is never shown, because the table
        is updated as soon as it tries to show it. So a setDataError
        signal is emitted with the text that can be used to show
        text in the status bar or something."""
        singleerror(self.parentWidget(), text)
        self.setDataError.emit(text)

    def saveSettings(self):
        cparser = PuddleConfig()
        cparser.set('table', 'fontsize', self.fontSize)
        rowsize = self.verticalHeader().defaultSectionSize()
        cparser.set('table', 'rowsize', rowsize)
        cparser.set('table', 'sort_fields', self.model().sortFields)
        cparser.set('table', 'sort_reverse', self.model().reverseSort)

    def nextDir(self, dirpaths, previous=False):
        taginfo = self.model().taginfo
        row = self.currentIndex().row()
        column = self.currentIndex().column()
        i = 0
        d = taginfo[row].dirpath
        while True:
            try:
                if d != taginfo[row + i].dirpath:
                    new_dir = taginfo[row + i].dirpath
                    break
            except IndexError:
                return
            if not previous:
                i += 1
                if row + i >= len(taginfo):
                    row = 0 - i
            else:
                i -= 1

        return dict((row, column) for row in dirpaths[new_dir])

    def selectPrevDir(self):
        return self.selectDir(True)

    def selectRow(self, row):
        selection = QItemSelection()
        get_index = self.model().index
        columns = self.selectedColumns
        for column in columns:
            index = get_index(row, column)
            selection.merge(QItemSelection(index, index),
                            QItemSelectionModel.Select)
        self.selectionModel().select(selection,
                                     QItemSelectionModel.ClearAndSelect)

        self.scrollTo(get_index(row, min(columns)), self.EnsureVisible)

    def selectDir(self, previous=False):
        model = self.model()
        modelindex = model.index
        selection = QItemSelection()
        merge = selection.merge
        taginfo = model.taginfo

        selected = defaultdict(lambda: [])
        selected_rows = set()

        for index in self.selectedIndexes():
            if index.row() not in selected_rows:
                selected[taginfo[index.row()].dirpath].append(index.column())
                selected_rows.add(index.row())

        dirpaths = defaultdict(lambda: set())

        dirs_sorted = []

        for row, f in enumerate(taginfo):
            dirpaths[f.dirpath].add(row)
            dirs_sorted.append(f.dirpath)

        to_select = {}

        for d, columns in selected.items():
            if len(columns) == len(dirpaths[d]) and len(selected) == 1:
                to_select = self.nextDir(dirpaths, previous)
                if to_select:
                    self.selectionModel().clearSelection()
                    self.setCurrentIndex(
                        modelindex(min(to_select), min(to_select.values())))
                else:
                    return
            else:
                for row in dirpaths[d]:
                    to_select[row] = columns[-1]

        for row, column in to_select.items():
            index = modelindex(row, column)
            merge(QItemSelection(index, index), QItemSelectionModel.Select)

        self.selectionModel().select(selection, QItemSelectionModel.Select)

    def showProperties(self):
        f = self.selectedTags[0]
        win = Properties(f.info, self.parentWidget())
        win.show()

    def setPlayCommand(self, command):
        self.playcommand = command

    def setTestData(self, data):
        if hasattr(data, 'items'):
            self.model().setTestData(data)
        else:
            self.model().setTestData(self.selectedRows, data)

    def sortByColumn(self, column):
        """Guess"""
        QTableView.sortByColumn(self, column)
        self.restoreSelection()

    def wheelEvent(self, e):
        h = self.horizontalScrollBar()
        if not self.verticalScrollBar().isVisible() and h.isVisible():
            numsteps = e.angleDelta().y() / 5
            h.setValue(h.value() - numsteps)
            e.accept()
        else:
            QTableView.wheelEvent(self, e)
