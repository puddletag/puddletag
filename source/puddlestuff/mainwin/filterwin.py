from PyQt4.QtGui import QWidget, QLabel, QComboBox, QLineEdit, QHBoxLayout
from PyQt4.QtCore import SIGNAL
from puddlestuff.puddleobjects import gettaglist
from puddlestuff.constants import BOTTOMDOCK

class FilterView(QWidget):
    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        self.emits = ['filter']
        self.receives = []
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Tag:"))
        self._tags = QComboBox()
        self._tags.addItems(['None', '__all'] + gettaglist())
        self._tags.setEditable(True)
        self._text = QLineEdit()
        hbox.addWidget(self._tags, 0)
        hbox.setMargin(0)
        hbox.addWidget(self._text, 1)
        self.setLayout(hbox)

        self.connect(self._text, SIGNAL("textChanged(QString)"),
                        self.valsChanged)
        self.connect(self._tags, SIGNAL("editTextChanged(QString)"),
                        self.valsChanged)

    def valsChanged(self, *args):
        tag = unicode(self._tags.currentText())
        text = unicode(self._text.text())
        if tag == 'None':
            tag = None
        else:
            tag = [z.strip() for z in tag.split('|') if z.strip()]
        self.emit(SIGNAL('filter'), tag, text)

control = ("Filter", FilterView, BOTTOMDOCK, True)