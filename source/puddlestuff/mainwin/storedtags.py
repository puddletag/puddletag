import os

from PyQt5.QtCore import QMutex, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .. import audioinfo
from ..audioinfo import tag_versions
from ..constants import LEFTDOCK, SELECTIONCHANGED
from ..puddleobjects import PuddleThread, natural_sort_key

mutex = QMutex()


def sort_dict(d):
    ret = []
    for key, val in d.items():
        if isinstance(val, str):
            ret.append((key, val))
        else:
            ret.extend((key, v) for v in val)
    ret.sort(key=lambda v: natural_sort_key(v[0]))
    return ret


class StoredTags(QScrollArea):
    def __init__(self, parent=None, status=None):
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
        self._grid.setContentsMargins(3, 3, 3, 3)
        widget.setLayout(self._grid)
        self.setWidget(widget)
        # widget.wheelEvent.connect(self._hScroll)

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
            if not os.path.exists(filepath):
                return
            try:
                audio = audioinfo._Tag(filepath)
                tags = tag_versions.tags_in_file(filepath)
            except (OSError, IOError) as e:
                audio = {'Error': [e.strerror]}

            if isinstance(audio, audioinfo.id3.Tag):
                if 'ID3v2.4' in tags:
                    tags.remove('ID3v2.4')
                if 'ID3v2.3' in tags:
                    tags.remove('ID3v2.3')
                if 'ID3v2.2' in tags:
                    tags.remove('ID3v2.2')
            elif hasattr(audio, 'apev2') and audio.apev2:
                if 'APEv2' in tags:
                    tags.remove('APEv2')

            ret = [(audio['__tag_read'], sort_dict(audio.usertags))]

            for tag in tags:
                if not tag == audio['__tag_read']:
                    try:
                        ret.append((tag, sort_dict(tag_versions.tag_values(filepath, tag))))
                    except:
                        continue
            return ret

        def _load(tags):
            # print 'loading', time.time()
            while self._loading:
                QApplication.processEvents()
            self._loading = True
            self._init()
            if not tags:
                self._loading = False
                return

            grid = self._grid

            offset = 1
            for title, values in tags:
                if not values:
                    continue
                t_label = QLabel(title)
                t_label.setFont(self._boldfont)
                grid.addWidget(t_label, offset - 1, 0)
                for row, (tag, value) in enumerate(values):
                    field = QLabel('%s:' % tag)
                    field.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                    grid.addWidget(field, row + offset, 0)
                    vlabel = QLabel(value)
                    grid.addWidget(vlabel, row + offset, 1)
                grid.setRowMinimumHeight(grid.rowCount(),
                                         vlabel.sizeHint().height())
                offset += grid.rowCount() + 1
            vbox = QVBoxLayout()
            vbox.addStretch()
            grid.addLayout(vbox, offset + 1 + offset, 0, -1, -1)
            grid.setRowStretch(offset + 1, 1)
            self._loading = False

        thread = PuddleThread(retrieve_tag, self)
        thread.threadfinished.connect(_load)
        # print 'starting thread', time.time()
        thread.start()

    def showEvent(self, event):
        super(StoredTags, self).showEvent(event)
        self.load()

    def wheelEvent(self, e):
        h = self.horizontalScrollBar()
        if not self.verticalScrollBar().isVisible() and h.isVisible():
            numsteps = e.angleDelta().y() / 5
            h.setValue(h.value() - numsteps)
            e.accept()
        else:
            QScrollArea.wheelEvent(self, e)


control = ('Stored Tags', StoredTags, LEFTDOCK, False)
