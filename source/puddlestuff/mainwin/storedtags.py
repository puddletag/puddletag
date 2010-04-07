import sys, os
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from puddlestuff.constants import LEFTDOCK
from puddlestuff.puddleobjects import PuddleThread, natcasecmp
from puddlestuff import audioinfo
import pdb

mutex = QMutex()

class StoredTags(QScrollArea):
    def __init__(self, parent=None, status = None):
        QScrollArea.__init__(self, parent)
        self.emits = []
        self.receives = self.receives = [('tagselectionchanged', self.load)]
        self._labels = []
        font = QFont()
        font.setBold(True)
        self._boldfont = font
        self._init()
        self.setWidgetResizable(True)

    def _init(self):
        widget = QWidget()
        self._grid = QGridLayout()
        self._grid.setColumnStretch(1, 1)
        self._grid.setMargin(3)
        widget.setLayout(self._grid)
        self.setWidget(widget)
        #self.connect(widget, SIGNAL('wheelEvent'), self._hScroll)

    def load(self, audios, selectedRows, selectedColumns):
        if hasattr(self, '_t') and self._t.isRunning():
            self._t.wait()
        locker = QMutexLocker(mutex)
        if audios:
            filepath = audios[0].filepath
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
            sortedvals = [[(key, val) for val in tags[key]]
                                    for key in sorted(tags, cmp = natcasecmp)]
            values = []
            [values.extend(v) for v in sortedvals]
            return values

        def _load(values):
            if self._t.isRunning():
                return
            self._init()
            if not values:
                return
            grid = self._grid
            for row, (tag, value) in enumerate(values):
                grid.addWidget(QLabel(u'%s:' % tag), row, 0)
                vlabel = QLabel(value)
                vlabel.setFont(self._boldfont)
                grid.addWidget(vlabel, row, 1)
            vbox = QVBoxLayout()
            vbox.addStretch()
            grid.addLayout(vbox,row + 1,0, -1, -1)
            grid.setRowStretch(row + 1, 1)

        self._t = PuddleThread(retrieve_tag)
        self._t.connect(self._t, SIGNAL('threadfinished'), _load)
        self._t.start()

    def wheelEvent(self, e):
        h = self.horizontalScrollBar()
        if not self.verticalScrollBar().isVisible() and h.isVisible():
            numsteps = e.delta() / 5
            h.setValue(h.value() - numsteps)
            e.accept()
        else:
            QScrollArea.wheelEvent(self, e)

control = ('Stored Tags', StoredTags, LEFTDOCK, False)