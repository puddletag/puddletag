import sys, os
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from puddlestuff.constants import RIGHTDOCK
from puddlestuff.puddleobjects import PuddleThread, natcasecmp
from puddlestuff import audioinfo
import pdb

mutex = QMutex()

class TestWidget(QWidget):
    def __init__(self, parent=None, status = None):
        QWidget.__init__(self, parent)
        self.emits = ['setpreview']
        self.receives = []
        button = QPushButton('Set Previews')
        self.connect(button, SIGNAL('clicked()'), self._changePreview)
        self._status = status

        box = QVBoxLayout()
        box.addWidget(button)
        self.setLayout(box)

    def _changePreview(self):
        status = self._status
        files = status['allfiles'][2:10]
        d = {}
        for f in files:
            d[f] = {'artist': 'Preview Artist', 'title': 'Preview Title'}
        self.emit(SIGNAL('setpreview'), d)

control = ('Puddle Testing', TestWidget, RIGHTDOCK, False)