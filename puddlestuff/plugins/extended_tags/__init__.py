from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence

from ...audioinfo import commontags
from ...constants import (LEFTDOCK, SELECTIONCHANGED,
                          KEEP)
from ...helperwin import BOLD, UNCHANGED, ExTags
from ... import puddletag
from ...puddleobjects import (settaglist)
from ...translations import translate


class ExTagsPlugin(ExTags):
    onetomany = pyqtSignal(dict, name='onetomany')

    def __init__(self, parent=None, row=None, files=None, status=False):
        self._status = status

        def set_pmode(v): self.previewMode = v

        self.receives = [
            (SELECTIONCHANGED, self.loadFiles),
            ('previewModeChanged', set_pmode)]
        self.emits = ['onetomany']

        super(ExTagsPlugin, self).__init__(parent, row, files, status, False)
        self.setMinimumSize(50, 50)

        self.okcancel.okButton.hide()
        self.okcancel.cancelButton.hide()

        # Delete elsewhere is Move to Trash's.
        self.listbuttons.removeButton.setShortcut(QKeySequence())
        self.table.installEventFilter(self)

        self.previewMode = False
        self.canceled = False
        self.filechanged = False

        if files:
            self.loadFiles(files)

        action = QAction(translate('Menus', 'Save Extended'), self)
        action.triggered.connect(self.save)
        action.setShortcut('Ctrl+Shift+S')

        def sep():
            k = QAction(self)
            k.setSeparator(True)
            return k

        puddletag.add_shortcuts('&Plugins', [sep(), action, sep()])

    def eventFilter(self, obj, event):
        if (obj is self.table and event.type() in (
                QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride)
                and event.key() == Qt.Key.Key_Delete):
            # Taking the override keeps Move to Trash's Del from competing.
            event.accept()
            if event.type() == QEvent.Type.KeyPress:
                self.listbuttons.removeButton.click()
            return True
        return super().eventFilter(obj, event)

    def loadFiles(self, audios=None):
        if audios is None:
            audios = self._status['selectedfiles']

        if not audios:
            self.table.clearContents()
            self.table.setRowCount(0)
            self.listbuttons.setEnabled(False)
            return

        self.listbuttons.setEnabled(True)

        self.filechanged = False
        self.table.clearContents()
        self.table.setRowCount(0)

        common, numvalues, imagetags = commontags(audios)
        if '__image' in common:
            del (common['__image'])
        previews = set(audios[0].preview)
        italics = set(audios[0].equal_fields())
        for audio in audios[1:]:
            previews = previews.intersection(audio.preview)
            italics = italics.intersection(audio.equal_fields())
        row = 0
        for field, values in common.items():
            if field in previews and field not in italics:
                preview = BOLD
            else:
                preview = UNCHANGED
            if numvalues[field] != len(audios):
                self._settag(row, field, KEEP)
                row += 1
            else:
                if isinstance(values, str):
                    self._settag(row, field, values, None, preview)
                    row += 1
                else:
                    for v in values:
                        self._settag(row, field, v, None, preview)
                        row += 1
        self._checkListBox()

    def save(self):
        if not self.filechanged:
            return
        tags = self.listtotag()
        newtags = [z for z in tags if z not in self.get_fieldlist]
        if newtags and newtags != ['__image']:
            settaglist(newtags + self.get_fieldlist)
        self.onetomany.emit(tags)


dialogs = [('Extended Tags', ExTagsPlugin, LEFTDOCK, False), ]
