# -*- coding: utf-8 -*-
#tagmodel.py

#Copyright (C) 2008-2009 concentricpuddle

#This file is part of puddletag, a semi-good music tag editor.

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNE SS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys,os, audioinfo, resource, pdb
from operator import itemgetter
from copy import copy, deepcopy
from subprocess import Popen
from os import path
import audioinfo
from audioinfo import (PATH, FILENAME, DIRPATH, EXTENSION,
    usertags, setmodtime, FILETAGS, READONLY, INFOTAGS, DIRNAME)
from puddleobjects import (unique, safe_name, partial, natcasecmp, gettag,
                           HeaderSetting, getfiles, ProgressWin, PuddleStatus,
                           PuddleThread, progress, PuddleConfig, singleerror,
                           winsettings, issubfolder, timemethod)
from musiclib import MusicLibError
import time, re
from errno import EEXIST
import traceback
from itertools import izip
from collections import defaultdict
from util import write, rename_file, real_filetags, to_string
from constants import SELECTIONCHANGED

status = {}

SETDATAERROR = SIGNAL("setDataError")
LIBRARY = '__library'
ENABLEUNDO = SIGNAL('enableUndo')
HIGHLIGHTCOLOR = Qt.green

def commontag(tag, tags):
    x = defaultdict(lambda: [])
    for audio in tags:
        if tag in audio:
            x[audio[tag][0]].append(audio)
        else:
            x[''].append(audio)
    return x

def loadsettings(filepath=None):
    settings = PuddleConfig()
    if filepath:
        settings.filename = filepath
    titles = settings.get('tableheader', 'titles',
                            ['Filename', 'Artist', 'Title', 'Album', 'Track',
                                'Length', 'Year', 'Bitrate', 'Genre',
                                'Comment', 'Dirpath'])
    tags = settings.get('tableheader', 'tags',
                        ['__filename', 'artist', 'title',
                            'album', 'track', '__length', 'year', '__bitrate',
                            'genre', 'comment', '__dirpath'])
    checked = settings.get('tableheader', 'enabled', range(len(tags)), True)
    fontsize = settings.get('table', 'fontsize', 0, True)
    rowsize = settings.get('table', 'rowsize', -1, True)
    v1_option = settings.get('id3tags', 'v1_option', 2)
    audioinfo.id3.v1_option = v1_option
    filespec = u';'.join(settings.get('table', 'filespec', []))
    return (zip(titles, tags), checked), fontsize, rowsize, filespec

def caseless(tag, audio):
    if tag in audio:
        return tag
    smalltag = tag.lower()
    try:
        return [z for z in audio if isinstance(z, basestring) and z.lower() == smalltag][0]
    except IndexError:
        return tag

def tag_in_file(tag, audio):
    if tag in audio:
        return tag
    smalltag = tag.lower()
    try:
        return [z for z in audio if z.lower() == smalltag][0]
    except IndexError:
        return None

def _Tag(model):
    splitext = path.splitext
    extensions = audioinfo.extensions
    options = audioinfo.options
    
    def ReplacementTag(filename):
        fileobj = file(filename, "rb")
        ext = splitext(filename)
        try:
            return extensions[ext][1](filename)
        except KeyError:
            pass

        try:
            header = fileobj.read(128)
            results = [Kind[0].score(filename, fileobj, header) for Kind in options]
        finally:
            fileobj.close()
        results = zip(results, options)
        results.sort()
        score, Kind = results[-1]
        
        class PreviewTag(Kind[1]):
            def __init__(self, *args, **kwargs):
                self.preview = {}
                super(PreviewTag, self).__init__(*args, **kwargs)
            
            def _get_images(self):
                if not self.IMAGETAGS:
                    return []
                if model.previewMode and '__image' in self.preview:
                    return self.preview['__image']
                else:
                    return Kind[1].images.fget(self)
            
            def _set_images(self, value):
                if not self.IMAGETAGS:
                    return
                if model.previewMode:
                    self.preview['__image'] = value
                else:
                    Kind[1].images.fset(self, value)
            
            images = property(_get_images, _set_images)

            def clear(self):
                self.preview.clear()
                super(PreviewTag, self).clear()

            def __delitem__(self, key):
                if key in INFOTAGS:
                    return
                if model.previewMode and key in self.preview:
                    del(self.preview[key])
                else:
                    super(PreviewTag, self).__delitem__(key)
            
            def delete(self):
                if self.preview:
                    preview = self.preview
                    self.preview = {}
                try:
                    Kind[1].delete(self)
                except:
                    self.preview = preview
                    raise

            def __getitem__(self, key):
                if model.previewMode and key in self.preview:
                    return self.preview[key]
                else:
                    return super(PreviewTag, self).__getitem__(key)

            def keys(self):
                keys = super(PreviewTag, self).keys()
                if model.previewMode and self.preview:
                    [keys.append(key) for key in self.preview 
                        if key not in keys]
                return keys

            def __len__(self):
                return len(self.keys())
                
            def realvalue(self, key):
                return Kind[1].__getitem__(self, key)
            
            def __setitem__(self, key, value):
                if model.previewMode:
                    if key in FILETAGS:
                        test_audio = audioinfo.MockTag()
                        test_audio.filepath = self[PATH]

                        if key == FILENAME:
                            test_audio.filename = safe_name(to_string(value))
                        elif key == EXTENSION:
                            test_audio.ext = safe_name(to_string(value))
                        elif key == PATH:
                            test_audio.filepath = value
                        
                        new_values = {FILENAME: test_audio.filename,
                            PATH: test_audio.filepath,
                            EXTENSION: test_audio.ext,
                            DIRNAME: test_audio.dirname,
                            DIRPATH: test_audio.dirpath}
                        
                        self.preview.update(new_values)

                    elif key not in READONLY:
                        if not value:
                            self.preview
                        if self[key] != value:
                            self.preview[key] = value

                    for k, v in self.preview.items():
                        if self.realvalue(k) == v:
                            del(self.preview[k])
                else:
                    super(PreviewTag, self).__setitem__(key, value)
            
            def remove_from_preview(self, key):
                if key == EXTENSION:
                    del(self.preview[key])
                elif key == FILENAME:
                    for k in [FILENAME, EXTENSION, PATH]:
                        if k in self.preview:
                            del(self.preview[k])
                elif key in FILETAGS:
                    for k in FILETAGS:
                        if k in self.preview:
                            del(self.preview[k])
                else:
                    del(self.preview[key])

        if score > 0: return PreviewTag(filename)
        else: return None
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
        [('File', [('Filename', u'/Hip Hop Songs/Nas-These Are Our Heroes .mp3'),
                  ('Size', u'6151 kB'),
                  ('Path', u'Nas - These Are Our Heroes .mp3'),
                  ('Modified', '2009-07-28 14:04:05'),
                  ('ID3 Version', u'ID3v2.4')]),
        ('Version', [('Version', u'MPEG 1 Layer 3'),
                    ('Bitrate', u'192 kb/s'),
                    ('Frequency', u'44.1 kHz'),
                    ('Mode', 'Stereo'),
                    ('Length', u'4:22')])]
        """
        QDialog.__init__(self,parent)
        winsettings('fileinfo', self)
        self.setWindowTitle('File Properties')
        self._load(info)

    def _load(self, info):
        vbox = QVBoxLayout()
        interaction = Qt.TextSelectableByMouse or Qt.TextSelectableByKeyboard
        for title, items in info:
            frame = QGroupBox(title)
            framegrid = QGridLayout()
            framegrid.setColumnStretch(1,1)
            for row, value in enumerate(items):
                property = QLabel(value[0] + u':')
                property.setTextInteractionFlags(interaction)
                framegrid.addWidget(property, row, 0)
                propvalue = QLabel(u'<b>%s</b>' % value[1])
                propvalue.setTextInteractionFlags(interaction)
                framegrid.addWidget(propvalue, row, 1)
            frame.setLayout(framegrid)
            vbox.addWidget(frame)
        close = QPushButton('Close')
        self.connect(close, SIGNAL('clicked()'), self.close)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(close)
        vbox.addLayout(hbox)
        self.setLayout(vbox)


class ColumnSettings(HeaderSetting):
    """A dialog that allows you to edit the header of a TagTable widget."""
    title = 'Columns'
    def __init__(self, parent = None, showok = False, status=None):
        (self.tags, checked), fontsize, rowsize, filespec = loadsettings()
        HeaderSetting.__init__(self, self.tags, parent, showok, True)
        if showok:
            winsettings('columnsettings', self)
        self.buttonlist.moveup.hide()
        self.buttonlist.movedown.hide()
        self.setWindowFlags(Qt.Widget)
        label = QLabel('Adjust visibility of columns.')
        self.grid.addWidget(label, 0, 0)
        items = [self.listbox.item(z) for z in range(self.listbox.count())]
        if not checked:
            checked = []
        [z.setCheckState(Qt.Checked) if i in checked else z.setCheckState(Qt.Unchecked)
                                for i,z in enumerate(items)]

    def applySettings(self, control = None):
        row = self.listbox.currentRow()
        if row > -1:
            self.tags[row][0] = unicode(self.textname.text())
            self.tags[row][1] = unicode(self.tag.text())
        checked = [z for z in range(self.listbox.count()) if self.listbox.item(z).checkState()]
        titles = [z[0] for z in self.tags]
        tags = [z[1] for z in self.tags]
        cparser = PuddleConfig()
        cparser.set('tableheader', 'titles', titles)
        cparser.set('tableheader', 'tags', tags)
        cparser.set('tableheader', 'enabled', checked)

        headerdata = [z for i, z in enumerate(self.tags) if i in checked]

        if control:
            control.setHeaderTags(headerdata)
            control.restoreSelection()
        else:
            self.emit(SIGNAL("headerChanged"), headerdata)

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
    def __init__(self, headerdata, taginfo = None):
        """Load tags.

        headerdata must be a list of tuples
        where the first item is the displayrole and the second
        the tag to be used as in [("Artist", "artist"), ("Title", title")].

        taginfo is a list of audioinfo.Tag objects."""

        QAbstractTableModel.__init__(self)
        self.alternateAlbumColors = True
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

        if taginfo is not None:
            self.taginfo = unique(taginfo)
            self.sort(*self.sortOrder)
        else:
            self.taginfo = []
            self.reset()
        for z in self.taginfo:
            z.preview = {}
            z.previewundo = {}
            z.undo = {}
            z.color = None
            if not hasattr(z, 'library'):
                z.library = None
        self.undolevel = 0
        self._fontSize = QFont().pointSize()

    def _setFontSize(self, size):
        self._fontSize = size
        top = self.index(self.rowCount(), 0)
        bottom = self.index(self.rowCount() -1, self.columnCount() -1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
            top, bottom)

    def _getFontSize(self):
        return self._fontSize

    fontSize = property(_getFontSize, _setFontSize)

    def _get_previewMode(self):
        return self._previewMode
    
    def _set_previewMode(self, value):
        if not value:
            rows = [row for row, audio in enumerate(self.taginfo) 
                if audio.preview]
            self.setTestData(rows, [{} for z in rows])
            self.undolevel = self._savedundolevel
        else:
            self._savedundolevel = self.undolevel
        self._previewMode = value
        self.emit(SIGNAL('previewModeChanged'), value)
    
    previewMode = property(_get_previewMode, _set_previewMode)

    def _getUndoLevel(self):
        return self._undolevel

    def _setUndoLevel(self, value):
        #print value
        if value == 0:
            self.emit(ENABLEUNDO, False)
        else:
            self.emit(ENABLEUNDO, True)
        self._undolevel = value

    undolevel = property(_getUndoLevel, _setUndoLevel)

    def applyFilter(self, tags, pattern=None, matchcase=True):
        self.taginfo = self.taginfo + self._filtered
        taginfo = self.taginfo
        if ((not tags) or (not pattern)) and (not self._filtered):
            return
        elif (not tags) or (not pattern):
            self._filtered = []
            self.reset()
            return

        pattern = re.compile(pattern)
        def filt(tags, audio, check):
            if check:
                for tag in tags:
                    if tag not in audio:
                        continue
                    elif isinstance(audio[tag], basestring):
                        if pattern.search(audio[tag]):
                            return True
                    else:
                        if [True for t in audio[tag] if pattern.search(t)]:
                            return True
            else:
                for tag in tags:
                    if isinstance(audio[tag], basestring):
                        if pattern.search(audio[tag]):
                            return True
                    else:
                        if [True for t in audio[tag] if pattern.search(t)]:
                            return True
            return False
        if tags == ['__all']:
            t = [filt(audio.keys(), audio, False) for audio in self.taginfo]
        else:
            t = [filt(tags, audio, True) for audio in self.taginfo]
        self._filtered = [taginfo[i] for i,z in enumerate(t) if not z]
        self.taginfo = [taginfo[i] for i,z in enumerate(t) if z]
        self.reset()

    def changeFolder(self, olddir, newdir):
        """Used for changing the directory of all the files in olddir to newdir.
        i.e. All children of olddir will now become children of newdir

        No actual moving is done though."""

        folder = itemgetter(DIRPATH)
        tags = [(i, z) for i, z in enumerate(self.taginfo)
                    if z.dirpath.startswith(olddir)]
        libtags = []
        for i, audio in tags:
            if audio.dirpath == olddir:
                audio.dirpath = newdir
            else: #Newdir is a parent
                audio.dirpath = newdir + audio.dirpath[len(olddir):]
            if audio.library:
                audio.save(True)
        rows = [z[0] for z in tags]
        if rows:
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                        self.index(min(rows), 0), self.index(max(rows),
                                                    self.columnCount() - 1))

    def columnCount(self, index=QModelIndex()):
        return len(self.headerdata)
    
    def _toString(self, val):
        if isinstance(val, basestring):
            return val.replace(u'\n', u' ')
        else:
            return '\\\\'.join(val).replace(u'\n', u' ')

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if not index.isValid() or not (0 <= row < len(self.taginfo)):
            return QVariant()
        if (role == Qt.DisplayRole) or (role == Qt.ToolTipRole) or (role == Qt.EditRole):
            try:
                audio = self.taginfo[row]
                tag = self.headerdata[index.column()][1]
                val = self._toString(audio[tag])

                if role == Qt.ToolTipRole and self.previewMode and \
                    audio.preview and tag in audio.preview:
                    try:
                        real = self._toString(audio.realvalue(tag))
                        if not real:
                            real = u'<blank>'
                    except KeyError:
                        real = u'<blank>'
                    tooltip = u'Preview: %s\nReal: %s' % (
                        val, self._toString(real))
                    return QVariant(tooltip)
                return QVariant(val)
            except (KeyError, IndexError):
                return QVariant()
        elif role == Qt.BackgroundColorRole:
            if self.taginfo[row].color:
                return QVariant(self.taginfo[row].color)
        elif role == Qt.FontRole:
            tag = self.headerdata[index.column()][1]
            f = QFont()
            if f.pointSize() != self.fontSize:
                f.setPointSize(self.fontSize)
            if tag in self.taginfo[row].preview:
                f.setBold(True)
            return QVariant(f)
        return QVariant()

    def deleteTag(self, row):
        audio = self.taginfo[row]
        uns = dict([(key, val) for key,val in audio.items()
                            if isinstance(key, (int, long))])
        tags = audio.usertags
        tags['__image'] = audio['__image']
        audio.delete()
        audio.undo[self.undolevel] = tags
        audio.update(uns)

    def deleteTags(self, rows):
        [self.deleteTag(row) for row in rows]
        self.undolevel += 1

    def dropMimeData(self, data, action, row, column, parent = QModelIndex()):
        return True

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index)|
                            Qt.ItemIsEditable| Qt.ItemIsDropEnabled)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
            return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            try:
                return QVariant(self.headerdata[section][0])
            except IndexError:
                return QVariant()
        return QVariant(long(section + 1))
    
    def highlight(self, rows):
        rows = rows[::]
        hcolor = QPalette().color(QPalette.Mid)
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
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                top, bottom)

    def insertColumns(self, column, count, parent = QModelIndex(), data=None):
        self.beginInsertColumns (parent, column, column + count)
        if data:
            self.headerdata.extend(data)
        else:
            self.headerdata += [("","") for z in range(count - column+1)]
        self.endInsertColumns()
        #self.emit(SIGNAL('modelReset')) #Because of the strange behaviour mentioned in reset.
        return True

    def load(self,taginfo, headerdata=None, append = False):
        """Loads tags as in __init__.
        If append is true, then the tags are just appended."""
        if headerdata is not None:
            self.headerdata = headerdata

        for z in taginfo:
            z.preview = {}
            z.undo = {}
            z.previewundo = {}
            z.color = None
            if not hasattr(z, 'library'):
                z.library = None

            #if self.alternateAlbumColors:
                #albums = commontag('album', taginfo)
                #colors = [QPalette().base().color(), QPalette().alternateBase().color()]
                #if hasattr(self, '_lasti'):
                    #i = self._lasti
                #else:
                    #i = 0
                #for tags in albums.values():
                    #for tag in tags:
                        #tag.color = colors[i]
                    #i = 0 if i else 1
                #self._lasti = i

        if append:
            column = self.sortOrder[0]
            tag = self.headerdata[column][1]
            if self.sortOrder[1] == Qt.AscendingOrder:
                taginfo = sorted(taginfo, natcasecmp, itemgetter(tag))
            else:
                taginfo = sorted(taginfo, natcasecmp, itemgetter(tag), True)
            filenames = [z.filepath for z in self.taginfo]
            self.taginfo.extend([z for z in taginfo if z.filepath
                                    not in filenames])

            first = self.rowCount()
            self.beginInsertRows(QModelIndex(), first, first + len(taginfo) - 1)
            self.endInsertRows()

            top = self.index(first, 0)
            bottom = self.index(self.rowCount() -1, self.columnCount() -1)
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                            top, bottom)
        else:
            top = self.index(0, 0)
            self.taginfo = taginfo
            self._filtered = []
            self.reset()
            self.sort(*self.sortOrder)
            [setattr(z, 'color', None) for z in self.taginfo if z.color]
            self.undolevel = 0

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
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                top, bottom)
    
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
        rows = map(row_index, tags + self._colored)
        if rows:
            top = self.index(min(rows), 0)
            bottom = self.index(max(rows), self.columnCount() - 1)
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                top, bottom)
        self._colored = tags

    def removeColumns(self, column, count, parent = QModelIndex()):
        self.beginRemoveColumns(QModelIndex(), column, column + count - 1)
        del(self.headerdata[column: column+count])
        self.endRemoveColumns()
        return True

    def removeFolders(self, folders, v = True):
        if v:
            f = [i for i, tag in enumerate(self.taginfo) if tag.dirpath
                            not in folders and not tag.library]
        else:
            f = [i for i, tag in enumerate(self.taginfo) if tag.dirpath
                                in folders and not tag.library]
        while f:
            try:
                self.removeRows(f[0])
                del(f[0])
                f = [z - 1 for z in f]
            except IndexError:
                break

    def removeRows(self, position, rows=1, index=QModelIndex()):
        """Please, only use this function to remove one row at a time. For some reason, it doesn't work
        too well on debian if more than one row is removed at a time."""
        self.beginRemoveRows(QModelIndex(), position,
                         position + rows -1)
        del(self.taginfo[position])
        self.endRemoveRows()
        return True

    def renameFile(self, row, tags):
        """If tags(a dictionary) contains a PATH key, then the file
        in self.taginfo[row] is renamed based on that.

        If successful, tags is returned(with the new filename as a key)
        otherwise {} is returned."""
        currentfile = self.taginfo[row]
        oldfilename = currentfile.filepath

        if PATH in tags:
            currentfile.filepath = tags[PATH]
        elif FILENAME in tags:
            currentfile.filename = tags[FILENAME]
        elif EXTENSION in tags:
            currentfile.ext = tags[EXTENSION]
        else:
            return

        newfilename = currentfile.filepath
        if newfilename != oldfilename:
            try:
                if os.path.exists(newfilename) and newfilename != oldfilename:
                    raise IOError(EEXIST, os.strerror(EEXIST), oldfilename)
                os.rename(oldfilename, newfilename)
            #I don't want to handle the error, but at the same time I want to know
            #which file the error occured at.
            except (IOError, OSError), detail:
                currentfile.filename = oldfilename
                self.emit(SIGNAL('fileError'), currentfile)
                raise detail

    def reset(self):
        #Sometimes, (actually all the time on my box, but it may be different on yours)
        #if a number files loaded into the model is equal to number
        #of files currently in the model then the TableView isn't updated.
        #Why the fuck I don't know, but this signal, intercepted by the table,
        #updates the view and makes everything work okay.
        self.emit(SIGNAL('modelReset'))
        QAbstractTableModel.reset(self)

    def rowColors(self, rows = None, clear=False):
        """Changes the background of rows to green.

        If rows is None, then the background of all the rows in the table
        are returned to normal."""
        taginfo = self.taginfo
        if rows:
            if clear:
                for row in rows:
                    if hasattr(taginfo[row], "color"):
                        del(taginfo[row].color)
            else:
                for row in rows:
                    taginfo[row].color = HIGHLIGHTCOLOR
                for i, z in enumerate(taginfo):
                    if i not in rows and hasattr(taginfo[row], "color"):
                        del(taginfo[row].color)
        else:
            rows = []
            for i, tag in enumerate(self.taginfo):
                if hasattr(tag, 'color'):
                    del(tag.color)
                    rows.append(i)
        if rows:
            firstindex = self.index(min(rows), 0)
            lastindex = self.index(max(rows), self.columnCount() - 1)
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                            firstindex, lastindex)

    def rowCount(self, index = QModelIndex()):
        return len(self.taginfo)

    def setData(self, index, value, role = Qt.EditRole):
        """Sets the data of the currently edited cell as expected.
        Also writes tags and increases the undolevel."""
        if index.isValid() and 0 <= index.row() < len(self.taginfo):
            column = index.column()
            tag = self.headerdata[column][1]
            currentfile = self.taginfo[index.row()]
            newvalue = unicode(value.toString())
            realtag = currentfile.mapping.get(tag, tag)
            if realtag in FILETAGS and tag not in [FILENAME, EXTENSION]:
                return False

            try:
                if tag not in FILETAGS:
                    newvalue = filter(None, newvalue.split(u'\\'))
                ret = self.setRowData(index.row(), {tag: newvalue})
                if currentfile.library:
                    self.emit(SIGNAL('libfilesedit'), ret[0], ret[1])
                self.undolevel += 1
            except EnvironmentError, detail:
                self.emit(SETDATAERROR, u"An error occurred while writing to"
                    " <b>%s</b>: (%s)" % (currentfile.filepath,
                                            detail.strerror))
                return False
            self.emit(SIGNAL('fileChanged()'))
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        index, index)
            return True
        return False

    def setHeaderData(self, section, orientation, value, role = Qt.EditRole):
        if (orientation == Qt.Horizontal) and (role == Qt.DisplayRole):
            self.headerdata[section] = value
        self.emit(SIGNAL("headerDataChanged (Qt::Orientation,int,int)"), orientation, section, section)

    def setHeader(self, tags):
        self.headerdata = tags
        self.reset()

    def setRowData(self,row, tags, undo = False, justrename = False):
        """A function to update one row.
        row is the row, tags is a dictionary of tags.

        If undo`is True, then an undo level is created for this file.
        If justrename is True, then (if tags contain a PATH or EXTENSION key)
        the file is just renamed i.e not tags are written.
        """
        audio = self.taginfo[row]

        if self.previewMode:
            preview = audio.preview
            undo = dict([(tag, copy(audio[tag])) if tag in audio
                else (tag, []) for tag in tags])
            audio.update(tags)
            audio.previewundo[self.undolevel] = undo
            return

        if justrename:
            filetags = real_filetags(audio.mapping, audio.revmapping, tags)
            undo = dict([(tag, copy(audio[tag])) if tag in audio
                else (tag, []) for tag in tags])
            rename_file(audio, filetags)
            if audio.library:
                audio.save(True)
            audio.undo[self.undolevel] = undo
        else:
            artist = audio.sget('artist')
            audio.undo[self.undolevel] = write(audio, tags, 
                self.saveModification)
            if audio.library:
                return (artist, tags)

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
            self.unSetTestData(rows = unsetrows)
        for row, preview in zip(rows, previews):
            taginfo[row].preview = preview
        firstindex = self.index(min(rows), 0)
        lastindex = self.index(max(rows),self.columnCount() - 1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        firstindex, lastindex)
        self.emit(SIGNAL('fileChanged()'))

    def sibling(self, row, column, index = QModelIndex()):
        if row < (self.rowCount() - 1) and row >= 0:
           return self.index(row + 1, column)

    def sort(self, column, order = Qt.DescendingOrder):
        self.emit(SIGNAL('aboutToSort'))
        self.sortOrder = (column, order)
        try:
            tag = self.headerdata[column][1]
        except IndexError:
            if len(self.headerdata) >= 1:
                tag = self.headerdata[0][1]
            else:
                return
        f = lambda audio: audio.get(tag, '')
        if order == Qt.AscendingOrder:
            self.taginfo.sort(natcasecmp, f)
        else:
            self.taginfo.sort(natcasecmp, f, True)
        self.reset()
        self.emit(SIGNAL('sorted'))

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
        oldfiles =  []
        newfiles = []
        rows = []
        edited = []
        for row, audio in enumerate(self.taginfo):
            if self.previewMode:
                undo_tags = audio.previewundo
                if level in undo_tags:
                    audio.update(undo_tags[level])
                    rows.append(row)
                    del(undo_tags[level])
            elif level in audio.undo:
                if audio.library:
                    oldfiles.append(audio.tags.copy())
                edited.append(self.setRowData(row, audio.undo[level]))
                rows.append(row)
                del(audio.undo[level])
        if rows:
            self.updateTable(rows)
            if edited:
                self.emit(SIGNAL('libfilesedited'), edited)
        if self.undolevel > 0:
            self.undolevel -= 1

    def unSetTestData(self, rows = None):
        taginfo = self.taginfo
        if not rows:
            rows = [i for i,z in enumerate(taginfo) if z.preview]
            if not rows:
                return
        for row in rows:
            taginfo[row].preview = {}

        if rows:
            firstindex = self.index(min(rows), 0)
            lastindex = self.index(max(rows), self.columnCount() - 1)
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                            firstindex, lastindex)

    def updateTable(self, rows):
        firstindex = self.index(min(rows), 0)
        lastindex = self.index(max(rows),self.columnCount() - 1)
        self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                                        firstindex, lastindex)

class TagDelegate(QItemDelegate):
    def __init__(self,parent=None):
        QItemDelegate.__init__(self,parent)

    def createEditor(self,parent,option,index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.installEventFilter(self)
        return editor

    def keyPressEvent(self, event):
        QItemDelegate.keyPressEvent(self, event)

    def commitAndCloseEditor(self):
        editor = self.sender()
        self.emit(SIGNAL("closeEditor(QWidget*, QAbstractItemDelegate::EndEditHint)"), editor, QItemDelegate.EditNextItem)

    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.EditRole).toString()
        editor.setText(text)

    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.text()))


class TableHeader(QHeaderView):
    """A headerview put here simply to enable the contextMenuEvent
    so that I can show the edit columns menu.

    Call it with tags in the usual form, to set the top header."""
    def __init__(self, orientation, tags = None, parent = None):
        QHeaderView.__init__(self, orientation, parent)
        if tags is not None: self.tags = tags
        self.setClickable(True)
        self.setHighlightSections(True)
        self.setMovable(True)
        self.setSortIndicatorShown(True)
        self.setSortIndicator(0, Qt.AscendingOrder)

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
        self.win = ColumnSettings(showok = True)
        self.win.setModal(True)
        self.win.show()
        self.connect(self.win, SIGNAL("headerChanged"), self.headerChanged)

    def headerChanged(self, val):
        self.emit(SIGNAL("headerChanged"), val)

class VerticalHeader(QHeaderView):
    def __init__(self, orientation, parent = None):
        QHeaderView.__init__(self, orientation, parent)
        self.setDefaultSectionSize(self.minimumSectionSize() + 3)
        self.setMinimumSectionSize(1)

        self.connect(self, SIGNAL('sectionResized(int,int,int)'), self._resize)

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

    def __init__(self, headerdata = None, parent = None):
        QTableView.__init__(self,parent)
        self.settingsdialog = ColumnSettings
        self.saveModification = True
        if not headerdata:
            headerdata = []
        header = TableHeader(Qt.Horizontal, headerdata, self)
        header.setSortIndicatorShown(True)
        self.setSortingEnabled(True)
        self._savedSelection = False
        #header.setStretchLastSection(True)

        self.setVerticalHeader(VerticalHeader(Qt.Vertical))

        #self.connect(header, SIGNAL("sectionClicked(int)"), self.sortByColumn)
        #header.setSortIndicator(0, Qt.AscendingOrder)
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
        self.connect(header, SIGNAL("headerChanged"), self.setHeaderTags)
        self.setModel(model)
        self.applyFilter = model.applyFilter

        def emitundo(val):
            self.emit(ENABLEUNDO, val)
            self.selectionChanged()
        self.connect(model, ENABLEUNDO, emitundo)
        self.connect(model, SIGNAL('libfilesedited'), lambda *args:
            self.emit(SIGNAL('libfilesedited'), *args))
        self.undo = model.undo

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
            'previewModeChanged']
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
            ('Show &row numbers', True),
            ('Automatically resize columns to contents', False),
            ('&Preserve file modification times', True),
            ('Program to &play files with:', 'amarok -p')
            ]

        status['selectedrows'] = self._getSelectedRows
        status['selectedfiles'] = self._selectedTags
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

    def _getSelectedTags(self):
        htags = [z[1] for z in self.model().headerdata]
        rows = self.currentRowSelection()
        audios = self.selectedTags

        ret = []
        for f, row in zip(audios, sorted(rows)):
            tags = (htags[column] for column in rows[row])
            ret.append(dict([(tag, f[tag]) for tag  in tags]))
        return ret

    def applyGenSettings(self, d, startlevel=None):
        self.saveSelection()
        if not startlevel:
            self.subFolders = d['Su&bfolders']
            self.setShowGrid(d['Show &gridlines'])
            self.verticalHeader().setVisible(d['Show &row numbers'])
            self.autoresize = d['Automatically resize columns to contents']
            self.saveModification = d['&Preserve file modification times']
            self.playcommand = d['Program to &play files with:'].split(' ')


    autoresize = property(_getResize, _setResize)

    def changeFolder(self, olddir, newdir):
      try:
        for i, d in enumerate(self.dirs[::]):
            if d == olddir:
                self.dirs[i] = newdir
            elif d.startswith(olddir):
                self.dirs[i] = newdir + d[len(olddir):]
      except IndexError:
        pass
      self.model().changeFolder(olddir, newdir)

    def clearAll(self):
        self.model().taginfo = []
        self.model().reset()
        self.emit(SIGNAL('dirschanged'), [])

    def removeTags(self):
        if self.model().previewMode:
            QMessageBox.information(self, 'puddletag',
                'Disable Preview Mode first to enable deleting of tags.')
            return
        deltag = self.model().deleteTag
        def func():
            for row in self.selectedRows:
                try:
                    deltag(row)
                    yield None
                except (OSError, IOError), e:
                    yield "There was an error deleting the tag of %s: <b>%s</b>" % (
                                e.filename, e.strerror), len(self.selectedRows)
                except NotImplementedError, e:
                    f = self.model().taginfo[row]
                    yield "There was an error deleting the tag of %s: " \
                        "<b>Tag deletion isn't supported for %s files.</b>" % (
                            f.filename, f.ext), len(self.selectedRows)
            self.model().undolevel += 1
            self.selectionChanged()

        f = progress(func, 'Deleting tag... ', len(self.selectedRows))
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
        self.deleteSelected(showmsg = False)

    def deleteSelected(self, delfiles=True, ifgone = False, showmsg = True):
        if delfiles and showmsg:
            result = QMessageBox.question (self, "puddletag",
                        "Are you sure you want to delete the selected files?",
                        "&Yes", "&No","", 1, 1)
        else:
            result = 0
        if result != 0:
            return
        selected = self.selectedTags
        selectedRows = self.selectedRows
        removeRows = self.model().removeRows
        curindex = self.currentIndex()
        last = max(selectedRows) - len(selectedRows) + 1, curindex.column()
        libtags = []
        def func():
            temprows = selectedRows[::]
            for ((i, row), audio) in izip(enumerate(selectedRows), selected):
                try:
                    filename = audio.filepath
                    os.remove(filename)
                    if audio.library:
                        audio.remove()
                        libtags.append(audio)
                    removeRows(temprows[i])
                    temprows = [z - 1 for z in temprows]
                    yield None
                except (OSError, IOError), detail:
                    msg = u"I couldn't delete <b>%s</b> (%s)" % (filename,
                            detail.strerror)
                    if row == temprows[-1]:
                        yield msg, 1
                    else:
                        yield msg, len(selectedRows)
        def fin():
            index = self.model().index(*last)
            if libtags:
                self.emit(SIGNAL('deletedfromlib'), libtags)
            if index.isValid():
                self.setCurrentIndex(index)
        s = progress(func, 'Deleting ', len(selectedRows), fin)
        if self.parentWidget():
            s(self.parentWidget())
        else:
            s(self)

    def dragEnterEvent(self, event):
        event.accept()
        event.acceptProposedAction()

    def dropEvent(self, event):
        files = [unicode(z.path()) for z in event.mimeData().urls()]
        while '' in files:
            files.remove('')
        self.loadFiles(files, append = True)

    def dragMoveEvent(self, event):
        if event.source() == self:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.accept()

    def mouseMoveEvent(self, event):

        if event.buttons() != Qt.LeftButton:
           return
        mimeData = QMimeData()
        plainText = ""
        tags= []
        if hasattr(self, "selectedRows"):
            selectedRows = self.selectedRows[::]
        else:
            return
        pnt = QPoint(*self.StartPosition)
        if (event.pos() - pnt).manhattanLength()  < QApplication.startDragDistance():
            return
        filenames = [z.filepath for z in self.selectedTags]
        urls = [QUrl.fromLocalFile(f) for f in filenames]
        mimeData = QMimeData()
        mimeData.setUrls(urls)

        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.setHotSpot(event.pos() - self.rect().topLeft())
        dropaction = drag.exec_()
        #if dropaction == Qt.MoveAction:
            #if not os.path.exists(filenames[0])
                #self.deleteSelected(False, True)

    def mousePressEvent(self, event):
        QTableView.mousePressEvent(self, event)
        if event.buttons()  == Qt.RightButton and self.model().taginfo:
            self.contextMenuEvent(event)
        if event.buttons() == Qt.LeftButton:
            self.StartPosition = [event.pos().x(), event.pos().y()]

    def fillTable(self, tags, append=False):
        """Clears the table and fills it with metadata in tags.

        tags are a list of audioinfo.Tag objects.
        If append is True then the tags are just appended.
        """
        self.selectedRows = []
        self.selectedColumns = []
        self.model().load(tags, append = append)

        if append:
            self.restoreSelection()
        else:
            self.selectCorner()

        if self.autoresize:
            self.resizeColumnsToContents()
        if self.model().taginfo:
            self.emit(SIGNAL('viewfilled'), True)
        else:
            self.emit(SIGNAL('viewfilled'), False)

    def highlight(self, rows):
        self.model().setColors(rows)

    def invertSelection(self):
        model = self.model()
        topLeft = model.index(0, 0);
        bottomRight = model.index(model.rowCount()-1, model.columnCount()-1)

        selection = QItemSelection(topLeft, bottomRight);
        self.selectionModel().select(selection, QItemSelectionModel.Toggle)

    def keyPressEvent(self, event):
        event.accept()
        #You might think that this is redundant since a delete
        #action is defined in contextMenuEvent, but if this isn't
        #done then the delegate is entered.
        if event.key() == Qt.Key_Delete and self.selectedRows:
            self.deleteSelected()
            return
        #This is so that an item isn't edited when the user's holding the shift or
        #control key.
        elif event.key() == Qt.Key_Space and (Qt.ControlModifier == event.modifiers() or Qt.ShiftModifier == event.modifiers()):
            trigger = self.editTriggers()
            self.setEditTriggers(self.NoEditTriggers)
            QTableView.keyPressEvent(self, event)
            self.setEditTriggers(trigger)
            return
        QTableView.keyPressEvent(self, event)

    def loadFiles(self, files=None, dirs=None, append=False, subfolders=None,
                    filepath=None):
        assert files or dirs, 'Either files or dirs (or both) must be specified.'

        if subfolders is None:
            subfolders = self.subFolders

        if not files:
            files = []
        if not dirs:
            dirs = []
        elif isinstance(dirs, basestring):
            dirs = [dirs]

        if dirs:
            for d in dirs:
                files = [z for z in files if not z.startswith(d)]

        if self.dirs:
            for d in self.dirs:
                files = [z for z in files if not z.startswith(d)]

        if append:
            self.saveSelection()
            if subfolders:
                #Remove all subfolders if the parent's already loaded.
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
        files = files + getfiles(dirs, subfolders, self.filespec)
        #[files.extend(z[1]) for z in getfiles(dirs, subfolders)]

        tags = []
        finished = lambda: self._loadFilesDone(tags, append, filepath)
        def what():
            isdir = os.path.isdir
            for f in files:
                tag = gettag(f)
                if tag is not None:
                    tags.append(tag)
                yield None

        s = progress(what, 'Loading ', len(files), finished)
        s(self.parentWidget())

    def _loadFilesDone(self, tags, append, filepath):
        self.fillTable(tags, append)
        if not filepath:
            self.emit(SIGNAL('dirschanged'), self.dirs)
        else:
            self.emit(SIGNAL('playlistchanged'), filepath)
        self.emit(SIGNAL('filesloaded'), True)
        if self._restore:
            self.clearSelection()
            self.restoreReloadSelection(*self._restore)
            self._restore = False

        model = self.model()
        model.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                    model.index(0,0), model.index(model.rowCount() -1,
                    model.columnCount() -1))
        self.selectionChanged()

    def load_tags(self, tags):
        self.fillTable(tags, False)
        self.dirs = []
        self.emit(SIGNAL('dirschanged'), self.dirs)
        self.emit(SIGNAL('filesloaded'), True)
        sortcolumn = self.horizontalHeader().sortIndicatorSection()
        QTableView.sortByColumn(self, sortcolumn)

    def loadSettings(self):
        (tags, checked), fontsize, rowsize, self.filespec = loadsettings()
        self.setHeaderTags([z for i, z in enumerate(tags) if i in checked])
        if fontsize:
            self.fontSize = fontsize
        if rowsize > -1:
            self.verticalHeader().setDefaultSectionSize(rowsize)

    def playFiles(self):
        """Play the selected files using the player specified in self.playcommand"""
        if not self.selectedRows: return
        if hasattr(self, "playcommand"):
            li = copy(self.playcommand)
            li.extend([z.filepath for z in self.selectedTags])
            try:
                Popen(li)
            except (OSError), detail:
                if detail.errno != 2:
                    QMessageBox.critical(self,"Error", u"I couldn't play the selected files: (<b>%s</b>) <br />Does the music player you defined (<b>%s</b>) exist?" % \
                                        (detail.strerror, u" ".join(self.playcommand)), QMessageBox.Ok, QMessageBox.NoButton)
                else:
                    QMessageBox.critical(self,"Error", u"I couldn't play the selected files, because the music player you defined (<b>%s</b>) does not exist." \
                                        % u" ".join(self.playcommand), QMessageBox.Ok, QMessageBox.NoButton)
    
    def previewMode(self, value):
        self.model().previewMode = value

    def reloadFiles(self, filenames = None):
        self._restore = self.saveSelection()
        files = [z.filepath for z in self.model().taginfo if z.dirpath
                        not in self.dirs]
        libfiles = [z for z in self.model().taginfo if '__library' in z]
        if self._playlist:
            self.loadFiles(files, self.dirs, False, self.subFolders)
        else:
            self.loadFiles(files, self.dirs, False, self.subFolders,
                            self._playlist)
        self.model().load(libfiles, append = True)

    def rowTags(self,row, stringtags = False):
        """Returns all the tags pertinent to the file at row."""
        if stringtags:
            return self.model().taginfo[row].stringtags()
        return self.model().taginfo[row]

    def selectCurrentColumn(self):
        if self.selectedIndexes():
            col = self.currentIndex().column()
            model = self.model()
            topLeft = model.index(0, col)
            bottomRight = model.index(model.rowCount()-1, col)

            selection = QItemSelection(topLeft, bottomRight);
            self.selectionModel().select(selection, QItemSelectionModel.Select)

    def selectCorner(self):
        topLeft = self.model().index(0, 0)
        selection = QItemSelection(topLeft, topLeft)
        self.selectionModel().select(selection, QItemSelectionModel.Select)
        #self.setFocus()

    def setModel(self, model):
        QTableView.setModel(self, model)
        self.updateRow = model.setRowData
        self.connect(model, SIGNAL('modelReset'), self.selectionChanged)
        self.connect(model, SETDATAERROR, self.writeError)
        self.connect(model, SIGNAL('fileChanged()'), self.selectionChanged)
        self.connect(model, SIGNAL('aboutToSort'), self.saveBeforeReset)
        self.connect(model, SIGNAL('sorted'), self.restoreSort)
        self.connect(model, SIGNAL('previewModeChanged'), 
            SIGNAL('previewModeChanged'))
        #self.connect(model, SIGNAL('modelReset()'), self.restoreAfterReset)

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

    def selectionChanged(self, selected = None, deselected = None):
        """Pretty important. This updates self.selectedRows, which is used
        everywhere.

        I've set selected an deselected as None, because I sometimes
        want self.selectedRows updated without hassle."""
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
        self.emit(SIGNAL('itemSelectionChanged()'))

        if self._select:
            if self.selectedRows:
                self.emit(SIGNAL('filesselected'), True)
            else:
                self.emit(SIGNAL('filesselected'), False)
            model.highlight(self.selectedRows)
            self.emit(SIGNAL(SELECTIONCHANGED))

    def saveBeforeReset(self):
        self.setCursor(Qt.BusyCursor)
        self._savedSelection = self.saveSelection()
    
    def restoreSort(self):
        self.setCursor(Qt.ArrowCursor)
        if self._savedSelection:
            self.restoreSelection(*self._savedSelection)
            self._savedSelection = None
            return

    def saveSelection(self):
        self._currentcol = self.currentColumnSelection()
        self._currentrow = self.currentRowSelection()
        self._currenttags = [(row, self.rowTags(row)) for row in self._currentrow]
        return (self._currentrow, self._currentcol, self._currenttags)

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
            del(tags[0])

        groups = {}
        for col, rows in currentcol.items():
            groups[col] = getGroups(sorted([newindexes[row] for row in rows if row in newindexes]))

        for col, rows in groups.items():
            [select(min(row), max(row), col) for row in rows]
        self.selectionModel().select(selection, QItemSelectionModel.Select)

    def restoreSelection(self, currentrow=None, currentcol=None, tags=None):
        if not currentrow:
            currentrow = self._currentrow
            currentcol = self._currentcol
            tags = self._currenttags
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

        getrow = self.model().taginfo.index
        modelindex = self.model().index
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
            newindexes[tag[0]] = getrow(tag[1])
            del(tags[0])
        groups = {}
        for col, rows in currentcol.items():
            groups[col] = getGroups(sorted([newindexes[row] for row in rows if row in newindexes]))

        for col, rows in groups.items():
            [select(min(row), max(row), col) for row in rows]
        self.selectionModel().clear()
        self.selectionModel().select(selection, QItemSelectionModel.Select)

    def removeFolders(self, dirs, valid = True):
        if dirs:
            self.dirs = list(set(self.dirs).difference(dirs))
            self.model().removeFolders(dirs, valid)

    def setHeaderTags(self, tags):
        self.saveSelection()
        self.model().setHeader(tags)
        self.restoreSelection()

    def setHorizontalHeader(self, header):
        QTableView.setHorizontalHeader(self, header)
        self.connect(header, SIGNAL('saveSelection'), self.saveSelection)

    def writeError(self, text):
        """Shows a tooltip when an error occors.

        Actually, a tooltip is never shown, because the table
        is updated as soon as it tries to show it. So a setDataError
        signal is emitted with the text that can be used to show
        text in the status bar or something."""
        singleerror(self.parentWidget(), text)
        self.emit(SETDATAERROR, text)

    def saveSettings(self):
        cparser = PuddleConfig()
        cparser.set('table', 'fontsize', self.fontSize)
        rowsize = self.verticalHeader().defaultSectionSize()
        cparser.set('table', 'rowsize', rowsize)

    def selectAllInFolder(self):
        model = self.model()
        modelindex = model.index
        selection = QItemSelection()
        merge = selection.merge
        taginfo = model.taginfo

        dirpaths = dict([(taginfo[index.row()].dirpath, index.column())
                            for index in self.selectedIndexes()])
        for row, audio in enumerate(model.taginfo):
            dirpath = audio.dirpath
            if dirpath in dirpaths:
                index = modelindex(row, dirpaths[dirpath])
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
            numsteps = e.delta() / 5
            h.setValue(h.value() - numsteps)
            e.accept()
        else:
            QTableView.wheelEvent(self, e)
