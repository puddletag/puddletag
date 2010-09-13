# -*- coding: utf-8 -*-
import sys, os
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from puddlestuff.constants import LEFTDOCK, SELECTIONCHANGED
from puddlestuff.puddleobjects import PuddleThread, natcasecmp
from puddlestuff import audioinfo
import pdb, time

mutex = QMutex()

class StoredTags(QScrollArea):
    def __init__(self, parent=None, status = None):
        QScrollArea.__init__(self, parent)
        self.emits = []
        self.receives = self.receives = [(SELECTIONCHANGED, self.load)]
        self._labels = []
        font = QFont()
        font.setBold(True)
        self._boldfont = font
        self._init()
        self.setWidgetResizable(True)
        self._status = status
        self._loading = False
        self._lastfilepath = None

    def _init(self):
        widget = QWidget()
        self._grid = QGridLayout()
        self._grid.setColumnStretch(1, 1)
        self._grid.setMargin(3)
        widget.setLayout(self._grid)
        self.setWidget(widget)
        #self.connect(widget, SIGNAL('wheelEvent'), self._hScroll)

    def load(self):
        audios = self._status['selectedfiles']
        if not self.isVisible():
            return
        if audios:
            filepath = audios[0].filepath
            if self._status['previewmode'] and filepath == self._lastfilepath:
                return
            self._lastfilepath = filepath
        else:
            self._init()
            return

        def retrieve_tag():
            try:
                audio = audioinfo.Tag(filepath)
            except (OSError, IOError), e:
                audio = {'Error': [e.strerror]}
            try:
                tags = audio.usertags
            except AttributeError:
                tags = audio

            sortedvals = [[(key, val) for val in tags[key]] if 
                not isinstance(tags[key], basestring) else [(key, tags[key])]
                for key in sorted(tags, cmp = natcasecmp)]
            values = []
            [values.extend(v) for v in sortedvals]
            return values

        def _load(values):
            #print 'loading', time.time()
            while self._loading:
                QApplication.processEvents()
            self._loading = True
            self._init()
            if not values:
                self._loading = False
                return
            grid = self._grid
            for row, (tag, value) in enumerate(values):
                field = QLabel(u'%s:' % tag)
                field.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                grid.addWidget(field, row, 0)
                vlabel = QLabel(value)
                vlabel.setFont(self._boldfont)
                grid.addWidget(vlabel, row, 1)
            vbox = QVBoxLayout()
            vbox.addStretch()
            grid.addLayout(vbox,row + 1,0, -1, -1)
            grid.setRowStretch(row + 1, 1)
            self._loading = False

        thread = PuddleThread(retrieve_tag, self)
        thread.connect(thread, SIGNAL('threadfinished'), _load)
        #print 'starting thread', time.time()
        thread.start()

    def wheelEvent(self, e):
        h = self.horizontalScrollBar()
        if not self.verticalScrollBar().isVisible() and h.isVisible():
            numsteps = e.delta() / 5
            h.setValue(h.value() - numsteps)
            e.accept()
        else:
            QScrollArea.wheelEvent(self, e)

control = ('Stored Tags', StoredTags, LEFTDOCK, False)