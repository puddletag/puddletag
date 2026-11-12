from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QWidget, QLineEdit, QPushButton)

from ..constants import BOTTOMDOCK
from ..puddleobjects import create_buddy, PuddleCombo
from ..translations import translate


class FilterView(QWidget):
    filter = pyqtSignal(str, name='filter')

    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        self.emits = ['filter']
        self.receives = []
        edit = QLineEdit()
        self.combo = PuddleCombo('filter_text')
        self.combo.setEditText('')
        self.combo.combo.setLineEdit(edit)
        hbox = create_buddy(translate("Defaults", "Filter: "), self.combo)
        go_button = QPushButton(translate('Defaults', 'Go'))
        hbox.addWidget(go_button)
        self.setLayout(hbox)

        emit_filter = lambda: self.filter.emit(
            str(edit.text()))
        go_button.clicked.connect(emit_filter)
        edit.returnPressed.connect(emit_filter)
        self.combo.combo.activated.connect(
            lambda i: emit_filter())

    def saveSettings(self):
        self.combo.save()


control = ("Filter", FilterView, BOTTOMDOCK, True)
