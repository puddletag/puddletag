# -*- coding: utf-8 -*-

import sys, pdb
import traceback
from puddlestuff.puddleobjects import (unique, OKCancel, PuddleThread,
    PuddleConfig, winsettings, natcasecmp)
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import QtCore, QtGui
from collections import defaultdict
from copy import deepcopy

from puddlestuff.tagsources import RetrievalError, status_obj, write_log
from puddlestuff.constants import TEXT, COMBO, CHECKBOX, RIGHTDOCK
from puddlestuff.findfunc import parsefunc
from functools import partial
from puddlestuff.util import pprint_tag, to_string
from puddlestuff.audioinfo import stringtags
from puddlestuff.translations import translate

CHECKEDFLAG = Qt.ItemIsEnabled |Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
NORMALFLAG = Qt.ItemIsEnabled | Qt.ItemIsSelectable

RETRIEVED_ALBUMS = translate('WebDB', 'Retrieved Albums (sorted by %s)')

default_albumpattern = u'%artist% - %album% $if(%__numtracks%, ' \
    u'[%__numtracks%], "")'

no_disp_fields = [u'__numtracks', u'__image']

pyqtRemoveInputHook()
def inline_display(pattern, tags):
    return parsefunc(pattern, tags)

def fillItem(item, info, tracks, trackpattern):
    item.itemData = info
    if tracks is not None:
        item.itemData['__numtracks'] = unicode(len(tracks))
        [item.appendChild(ChildItem(track, trackpattern, item))
                    for track in tracks]
        item.hasTracks = True
    else:
        item.itemData['__numtracks'] = u'0'
        item.hasTracks = False
    item.dispPattern = item.dispPattern

def get_tagsources():
    from puddlestuff.tagsources import exampletagsource, musicbrainz
    return exampletagsource.info[0](), musicbrainz.info[0]()

def strip(audio, taglist, reverse = False, mapping=None):
    if not taglist:
        if mapping:
            return dict([(mapping.get(key, key), audio[key]) for 
                key in audio if not key.startswith('#')])
        else:
            return dict([(key, audio[key]) for key in audio if 
                        not key.startswith('#')])
    tags = taglist[::]
    if tags and tags[0].startswith('~'):
        reverse = True
        tags[0] = tags[0][1:]
    else:
        reverse = False
    if reverse:
        if mapping:
            return dict([(mapping.get(key, key), audio[key]) for key in audio if key not in
                tags and not key.startswith('#')])
        else:
            return dict([(key, audio[key]) for key in audio if key not in
                tags and not key.startswith('#')])
    else:
        if mapping:
            return dict([(mapping.get(key, key), audio[key]) for 
                key in taglist if key in audio and not key.startswith('#')])
        else:
            return dict([(key, audio[key]) for key in taglist if 
                key in audio and not key.startswith('#')])

def tooltip(tag, mapping = None):
    """Used to display tags in in a human parseable format."""
    if not tag:
        return translate("WebDB", "<b>Error in pattern</b>")
    mapping = {} if mapping is None else mapping
    tag = dict((mapping.get(k, k), v) for k,v in tag.iteritems()
        if not k.startswith('#'))
        
    return pprint_tag(tag)

class Header(QHeaderView):
    def __init__(self, parent = None):
        QHeaderView.__init__(self, Qt.Horizontal, parent)
        self.setClickable(True)
        self.setStretchLastSection(True)
        self.setSortIndicatorShown(True)
        self.setSortIndicator(0, Qt.AscendingOrder)
        self.sortOptions = [z.split(',') for z in 
            [u'artist,album', u'album,artist', u'__numtracks,album']]

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        def create_action(order):
            action = QAction(u'/'.join(order), menu)
            slot = lambda: self.emit(SIGNAL('sortChanged'), order[::])
            self.connect(action, SIGNAL('triggered()'), slot)
            menu.addAction(action)

        [create_action(order) for order in self.sortOptions]
        menu.exec_(event.globalPos())

class RootItem(object):
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []


    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 1

    def data(self, column):
        return self.itemData[0]

    def parent(self):
        return None

    def row(self):
        return 0
    
    def sort(self, order=None, reverse=False):
        sortfunc = lambda item: u''.join([
            to_string(item.itemData.get(key, u'')) for key in order]).lower()
        self.childItems.sort(natcasecmp, sortfunc, reverse)
        

class TreeItem(RootItem):
    def __init__(self, data, pattern, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []
        self._display = ''
        self.dispPattern = pattern
        self.hasTracks = True
        self.expanded = False
        self.retrieving = False
    
    def data(self, column):
        return self._display
    
    def _getDisp(self):
        return self._pattern
    
    def _setDisp(self, pattern):
        self._pattern = pattern
        self._display = inline_display(pattern, self.itemData)
    
    dispPattern = property(_getDisp, _setDisp)

    def exact_matches(self):
        ret = []
        for c in self.childItems:
            if c.exact is not None:
                track = c.track()
                track['#exact'] = c.exact
                ret.append(track)
        return ret
    
    def tracks(self):
        if self.hasTracks:
            info = self.itemData.copy()
            if u'__numtracks' in info:
                del(info[u'__numtracks'])
            def get_track(item):
                track = info.copy()
                track.update(item.itemData.copy())
                return track
            return [get_track(item) for item in self.childItems]
        else:
            return None
    
    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

class ChildItem(RootItem):   
    def __init__(self, data, pattern, parent=None):
        self.parentItem = parent
        self.itemData = data
        if u'#exact' in data:
            self.checked = True
            self.exact = data['#exact']
        else:
            self.exact = None
        self.childItems = []
        self._display = ''
        self.dispPattern = pattern
        self.hasTracks = False

    def data(self, column):
        return self._display
    
    def _getDisp(self):
        return self._pattern
    
    def _setDisp(self, pattern):
        self._pattern = pattern
        self._display = inline_display(pattern, self.itemData)

    dispPattern = property(_getDisp, _setDisp)
    
    def track(self):
        track = self.parentItem.itemData.copy()
        if u'__numtracks' in track:
            del(track['__numtracks'])
        track.update(self.itemData.copy())
        return track
    
    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

class TreeModel(QtCore.QAbstractItemModel):
    def __init__(self, data = None, album_pattern=None, 
        track_pattern='%track% - %title%', tagsource=None, parent=None):
        QtCore.QAbstractItemModel.__init__(self, parent)
        
        self.mapping = {}
        rootData = map(QtCore.QVariant, [translate("WebDB", 'Retrieved Albums')])
        self.rootItem = RootItem(rootData)
        
        self._albumPattern = ''
        if album_pattern is None:
            self.albumPattern = default_albumpattern
        else:
            self.albumPattern = album_pattern
        self._sortOrder = ['album', 'artist']
        self._trackPattern = ''
        self.trackPattern = track_pattern
        self.tagsource = tagsource
        icon = QWidget().style().standardIcon
        self.expandedIcon = icon(QStyle.SP_DirOpenIcon)
        self.collapsedIcon = icon(QStyle.SP_DirClosedIcon)

        if data:
            self.setupModelData(data)

    def _get_albumPattern(self):
        return self._albumPattern
    
    def _set_albumPattern(self, value):
        self._albumPattern = value
        for item in self.rootItem.childItems:
            item.dispPattern = value
        parent = QModelIndex()
        top = self.index(0,0, parent)
        bottom = self.index(self.rowCount(parent) - 1, 0, parent)
        self.emit(SIGNAL('dataChanged (const QModelIndex&, const '
            'QModelIndex&)'), top, bottom)

    albumPattern = property(_get_albumPattern, _set_albumPattern)

    def _get_sortOrder(self):
        return self._sortOrder
    
    def _set_sortOrder(self, value):
        self._sortOrder = value
        self.sort()
    
    sortOrder = property(_get_sortOrder, _set_sortOrder)

    def _get_trackPattern(self):
        return self._trackPattern
    
    def _set_trackPattern(self, value):
        self._trackPattern = value
        for row, parent_item in enumerate(self.rootItem.childItems):
            if parent_item.childItems and parent_item.hasTracks:
                for track in parent_item.childItems:
                    track.dispPattern = value
                parent_index = self.index(row, 0, QModelIndex())
                top = self.index(0,0, parent_index)
                bottom = self.index(self.rowCount(parent_index)
                    - 1, 0, parent_index)
                self.emit(SIGNAL('dataChanged (const QModelIndex&, const '
                        'QModelIndex&)'), top, bottom)

    trackPattern = property(_get_trackPattern, _set_trackPattern)

    def canFetchMore(self, index):
        item = index.internalPointer()
        if item in self.rootItem.childItems and not item.childItems \
            and item.hasTracks:
            return True
        return False

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()

        if role == Qt.DisplayRole:
            item = index.internalPointer()
            return QVariant(item.data(index.column()))
        elif role == Qt.ToolTipRole:
            item = index.internalPointer()
            return QVariant(tooltip(item.itemData, self.mapping))
        elif role == Qt.DecorationRole:
            item = index.internalPointer()
            if self.isTrack(item):
                return None
            if item.expanded:
                return QVariant(self.expandedIcon)
            else:
                return QVariant(self.collapsedIcon)
        elif role == Qt.CheckStateRole:
            item = index.internalPointer()
            if self.isTrack(item) and '#exact' in item.itemData:
                if item.checked:
                    return QVariant(Qt.Checked)
                else:
                    return QVariant(Qt.Unchecked)
        return QVariant()

    def fetchMore(self, index):
        item = index.internalPointer()
        if item.retrieving:
            return
        self.emit(SIGNAL('retrieving'))
        def fetch_func():
            try:
                return self.tagsource.retrieve(item.itemData)
            except RetrievalError, e:
                self.emit(SIGNAL("statusChanged"), 
                    translate("WebDB", 'An error occured: %1').arg(unicode(e)))
                return
            except Exception, e:
                traceback.print_exc()
                self.emit(SIGNAL("statusChanged"),
                    translate("WebDB", 'An unhandled error occured: %1').arg(unicode(e)))
                return

        item.retrieving = True
        thread = PuddleThread(fetch_func, self)
        self.emit(SIGNAL("statusChanged"), translate("WebDB", "Retrieving album tracks..."))
        thread.start()
        while thread.isRunning():
            QApplication.processEvents()
        val = thread.retval
        if val:
            info, tracks = val
            fillItem(item, info, tracks, self.trackPattern)
            self.emit(SIGNAL("statusChanged"), translate("WebDB", "Retrieval complete."))
            item.retrieving = False
        else:
            if not item.childCount():
                self.emit(SIGNAL('collapse'), index)
        self.emit(SIGNAL('retrievalDone()'))

    def hasChildren(self, index):
        item = index.internalPointer()
        if not item:
            return True
        if not item.hasTracks:
            return False
        if (item == self.rootItem) or (item in self.rootItem.childItems):
            if not item.retrieving:
                return True
        return False
    
    def isTrack(self, item):
        if (item == self.rootItem) or (item in self.rootItem.childItems):
            return False
        return True
    
    def flags(self, index):
        item = index.internalPointer()
        if self.isTrack(item) and '#exact' in item.itemData:
            return CHECKEDFLAG
        return NORMALFLAG

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and \
            role == QtCore.Qt.DisplayRole:
            ret = RETRIEVED_ALBUMS % u' / '.join(self.sortOrder)
            
            return QVariant(QString(ret))

        return QtCore.QVariant()

    def index(self, row, column, parent):
        if row < 0 or column < 0 or row >= self.rowCount(parent) or \
            column >= self.columnCount(parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def retrieve(self, index, fin_func=None):
        item = index.internalPointer()
        if (not self.tagsource) or (item not in self.rootItem.childItems) or \
            (item.childItems) or not item.hasTracks:
            return
        self.emit(SIGNAL('retrieving'))
        def retrieval_func():
            try:
                return self.tagsource.retrieve(item.itemData)
            except RetrievalError, e:
                self.emit(SIGNAL("statusChanged"), 
                    translate("WebDB", 'An error occured: %1').arg(unicode(e)))
                return None
            except Exception, e:
                traceback.print_exc()
                self.emit(SIGNAL("statusChanged"),
                    translate("WebDB", 'An unhandled error occured: %1').arg(unicode(e)))
                return None

        def finished(val):
            if val is None:
                self.emit(SIGNAL('retrievalDone()'))
                return
            fillItem(item, val[0], val[1], self.trackPattern)
            item.retrieving = False
            self.emit(SIGNAL('dataChanged (const QModelIndex&, const '
                'QModelIndex&)'), index, index)
            self.emit(SIGNAL("statusChanged"), translate("WebDB", "Retrieval complete."))
            self.emit(SIGNAL('retrievalDone()'))
            if fin_func:
                fin_func()

        item.retrieving = True
        self.emit(SIGNAL("statusChanged"), translate("WebDB", "Retrieving tracks..."))
        thread = PuddleThread(retrieval_func, parent=self)
        thread.connect(thread, SIGNAL('threadfinished'), finished)
        thread.start()

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def setData(self, index, value, role = Qt.CheckStateRole):
        if index.isValid() and self.isTrack(index):
            item = index.internalPointer()
            item.checked = not item.checked
            self.emit(SIGNAL('exactChanged'), item)
            return True

    def setupModelData(self, data):
        exact_matches = []
        self.rootItem.childItems = []
        for info, tracks in data:
            parent = TreeItem(info, self.albumPattern, self.rootItem)
            fillItem(parent, info, tracks, self.trackPattern)
            exact_matches.extend(parent.exact_matches())
            self.rootItem.appendChild(parent)
        self.sort()
        if exact_matches:
            self.emit(SIGNAL('exactMatches'), exact_matches)

    def sort(self, column=0, order=Qt.AscendingOrder):
        if order == Qt.AscendingOrder:
            self.rootItem.sort(self.sortOrder)
        else:
            self.rootItem.sort(self.sortOrder, True)
        self.reset()

class ReleaseWidget(QTreeView):
    def __init__(self, status, tagsource, parent=None):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(self.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setExpandsOnDoubleClick(False)
        self._tagSource = tagsource
        self._status = status
        self.tagsToWrite = []
        self.reEmitTracks = self.selectionChanged
        self.lastSortIndex = 0
        self.mapping = {}

        self.trackBound = 0.7
        self.albumBound = 0.7
        self.jfdi = True
        self.matchFields = ['artist', 'title']

        header = Header(self)
        self.connect(header, SIGNAL('sortChanged'), self.sort)
        self.setHeader(header)
        model = TreeModel()
        self.setModel(model)

    def _get_albumPattern(self):
        return self._albumPattern
    
    def _set_albumPattern(self, value):
        self._albumPattern = value
        self.model().albumPattern = value

    albumPattern = property(_get_albumPattern, _set_albumPattern)
    
    def _get_trackPattern(self):
        return self._trackPattern
    
    def _set_trackPattern(self, value):
        self._trackPattern = value
        self.model().trackPattern = value

    trackPattern = property(_get_trackPattern, _set_trackPattern)
    
    def _get_tagSource(self):
        return self._tagSource
    
    def _set_tagSource(self, source):
        self._tagSource = source
        self.model().tagsource = source
    
    tagSource = property(_get_tagSource, _set_tagSource)

    def cleanTrack(self, track):
        return strip(track, self.tagsToWrite, mapping=self.mapping)
    
    def emitExactMatches(self, item, files):
        if not item.hasTracks:
            return
        preview = {}
        from puddlestuff.masstag import match_files
        tracks = item.tracks()
        copies = []
        for f in files:
            cp = deepcopy(f)
            cp.cls = f
            copies.append(cp)

        exact = match_files(copies, tracks, self.trackBound, self.matchFields,
            self.jfdi, False)
        ret = {}
        for f, t in exact.items():
            t = strip(t, self.tagsToWrite, mapping=self.mapping)
            ret[f] = t
        self.emit(SIGNAL('exact'), ret)
        return ret

    def emitInitialExact(self, exact):
        ret = {}
        
        for track in exact:
            ret[track['#exact']] = self.cleanTrack(track)

        self.emit(SIGNAL('exactMatches'), ret)
    
    def emitTracks(self, tracks):
        tracks = map(dict, tracks)
        tracks = map(self.cleanTrack, tracks)
        #import pdb
        #pdb.set_trace()
        if tracks:
            self.emit(SIGNAL('preview'), 
                tracks[:len(self._status['selectedrows'])])
        else:
            rows = self._status['selectedrows']
            self.emit(SIGNAL('preview'), map(lambda x: {}, rows))
    
    def exactChanged(self, item):
        if item.checked:
            track = strip(item.itemData, self.tagsToWrite, 
                mapping = self.mapping)
            self.emit(SIGNAL('preview'), {item.itemData['#exact']: track})
        else:
            self.emit(SIGNAL('preview'), {item.itemData['#exact']: {}})

    def selectionChanged(self, selected=None, deselected=None):
        if selected or deselected:
            QTreeView.selectionChanged(self, selected, deselected)
        model = self.model()
        isTrack = model.isTrack

        items = [index.internalPointer() for index in self.selectedIndexes()]
        if len(items) == 1 and not isTrack(items[0]) \
            and not items[0].hasTracks:
            copytag = items[0].itemData.copy
            tags = self.tagsToWrite
            tracks = [strip(copytag(), tags, mapping=self.mapping) for z in 
                self._status['selectedrows']]
        else:
            singles = []
            albums = []
            [singles.append(item) if isTrack(item) else 
                albums.append(item) for item in items]
            tracks = []
            for item in singles:
                if not item.parentItem in albums:
                    tracks.append(item.track())
            [tracks.extend(item.tracks()) for item in albums 
                if item.hasTracks]
            for item in albums:
                if u'#extrainfo' in item.itemData:
                    desc, url = item.itemData[u'#extrainfo']
                    self.emit(SIGNAL('infoChanged'), 
                        u'<a href="%s">%s</a>' % (url, desc))
                    break
        self.emitTracks(tracks)
        self.emit(SIGNAL('itemSelectionChanged()'))

    def _setCollapsedFlag(self, index):
        item = index.internalPointer()
        item.expanded = False
    
    def _setExpandedFlag(self, index):
        item = index.internalPointer()
        item.expanded = True

    def setModel(self, model):
        QTreeView.setModel(self, model)
        connect = lambda signal, slot: self.connect(self, SIGNAL(signal), 
            slot)
        modelconnect = lambda signal, slot: self.connect(model,
            SIGNAL(signal), slot)
        func = partial(model.retrieve, fin_func=self.selectionChanged)
        #connect('activated (const QModelIndex&)', func)
        connect('expanded (const QModelIndex&)', self._setExpandedFlag)
        connect('collapsed (const QModelIndex&)', self._setCollapsedFlag)
        connect('clicked (const QModelIndex&)', func)
        self.connect(model, SIGNAL('statusChanged'), SIGNAL('statusChanged'))
        self.connect(model, SIGNAL('exactChanged'), self.exactChanged)
        modelconnect('exactMatches', self.emitInitialExact)
        modelconnect('retrieving', SIGNAL('retrieving'))
        modelconnect('retrievalDone()', SIGNAL('retrievalDone()'))
        modelconnect('retrieving', lambda: self.setEnabled(False))
        modelconnect('retrievalDone()', lambda: self.setEnabled(True))
        modelconnect('collapse', self.collapse)
        model.tagsource = self.tagSource
        model.mapping = self.mapping
    
    def setReleases(self, releases, files=None):
        from puddlestuff.masstag import find_best
        self.model().setupModelData(releases)
        #FIXME: The expander isn't shown if I don't do this. However
        #I can still click on it...Qt bug probably.
        QApplication.processEvents()
        
        if files:
            matches = find_best(releases, files, self.albumBound)
            if not matches:
                self.emit(SIGNAL('statusChanged'), translate(
                    'WebDB', 'No matching albums were found.'))
            elif len(matches) > 1:
                self.emit(SIGNAL('statusChanged'), translate(
                    'WebDB', 'More than one album matches. None will be retrieved.'))
            else:
                self.emit(SIGNAL('statusChanged'), translate(
                    'WebDB', 'Retrieving album.'))
                model = self.model()
                children = [z.itemData for z in model.rootItem.childItems]
                if children:
                    row = children.index(matches[0][0])
                    index = model.index(row, 0, QModelIndex())
                    x = lambda: self.emitExactMatches(
                        model.rootItem.childItems[row], files)
                    model.retrieve(index, x)
    
    def setSortOptions(self, options):
        self.header().sortOptions = options
    
    def sort(self, order):
        self.model().sortOrder = order
        self.model().sort()
        if order in self.header().sortOptions:
            self.lastSortIndex = self.header().sortOptions.index(order)
    
    def setMapping(self, mapping):
        self.model().mapping = mapping
        self.mapping = mapping

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    model = TreeModel()
    model.setupModelData(data)

    view = ReleaseWidget(1,get_tagsources()[0])
    view.setModel(model)
    view.setWindowTitle("Simple Tree Model")
    view.show()
    sys.exit(app.exec_())
