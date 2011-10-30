# -*- coding: utf-8 -*-
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from puddlestuff.constants import (LEFTDOCK, SELECTIONCHANGED,
    FILESSELECTED, KEEP, BLANK)
from puddlestuff.plugins import add_shortcuts, connect_shortcut
from puddlestuff.helperwin import (BOLD, UNCHANGED, ITALICS, EditField,
    ExTags)
from puddlestuff.puddleobjects import (settaglist)
from puddlestuff.audioinfo import commontags

class ExTagsPlugin(ExTags):
    def __init__(self, parent = None, row=None, files=None, status=False):
        super(ExTags, self).__init__(parent)

        self._status = status

        def set_pmode(v): self.previewMode = v
        
        self.receives = [
            (SELECTIONCHANGED, self.loadFiles),
            ('previewModeChanged', set_pmode)]
        self.emits = ['onetomany']

        super(ExTagsPlugin, self).__init__(parent, row, files, status, False)
        self.setMinimumSize(50,50)

        self.okcancel.ok.hide()
        self.okcancel.cancel.hide()

        self.previewMode = False
        self.canceled = False
        self.filechanged = False

        if files:
            self.loadFiles(files)

        action = QAction('Save Extended', self)
        self.connect(action, SIGNAL('triggered()'), self.save)
        action.setShortcut('Ctrl+Shift+S')

        def sep():
            k = QAction(self)
            k.setSeparator(True)
            return k
        add_shortcuts('&Plugins', [sep(), action, sep()])

    def addTag(self):
        win = EditField(parent=self, taglist=self.get_fieldlist)
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.editTagBuddy)

    def _imageChanged(self):
        self.filechanged = True

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
            del(common['__image'])
        previews = set(audios[0].preview)
        italics = set(audios[0].equal_fields())
        for audio in audios[1:]:
            previews = previews.intersection(audio.preview)
            italics = italics.intersection(audio.equal_fields())
        row = 0
        for field, values in common.iteritems():
            if field in previews and field not in italics:
                preview = BOLD
            else:
                preview = UNCHANGED
            if numvalues[field] != len(audios):
                self._settag(row, field, KEEP)
                row += 1
            else:
                if isinstance(values, basestring):
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
        tags.update({'__image': self._status['images']})
        self.emit(SIGNAL('onetomany'), tags)

    def _tag(self, row, status = None):
        getitem = self.table.item
        item = getitem(row, 0)
        tag = unicode(item.text())
        value = unicode(getitem(row, 1).text())
        if status:
            return (tag, value, item.status)
        else:
            return (tag, value)

dialogs = [('Extended Tags', ExTagsPlugin, LEFTDOCK, False),]