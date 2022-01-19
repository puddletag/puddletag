import glob
import os
from copy import deepcopy
from functools import partial

from PyQt5.QtCore import QMutex, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, \
    QLineEdit, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget

from .. import masstag
from ..constants import RIGHTDOCK
from ..masstag import (NO_MATCH_OPTIONS, fields_from_text, match_files, masstag, merge_tsp_tracks,
                       split_files, MassTagFlag, MassTagProfile, TagSourceProfile)
from ..masstag.config import (PROFILEDIR, convert_mtps,
                              load_all_mtps, save_mtp)
from ..puddleobjects import (create_buddy, winsettings, ListButtons, ListBox, OKCancel, PuddleConfig, PuddleThread)
from ..translations import translate


class _SignalObject(QObject):
    statusChanged = pyqtSignal(str, name='statusChanged')
    logappend = pyqtSignal(str, name='logappend')


status_obj = _SignalObject()


def set_status(msg):
    status_obj.statusChanged.emit(msg)
    QApplication.processEvents()


masstag.set_status = set_status

mutex = QMutex()


def search_error(error, profile):
    set_status(translate('Masstagging',
                         'An error occured during the search: <b>%s</b>') % str(error))


def retrieval_error(error, profile):
    set_status(translate('Masstagging',
                         'An error occured during album retrieval: <b>%s</b>') % str(error))


class MassTagEdit(QDialog):
    profilesChanged = pyqtSignal(list, name='profilesChanged')

    def __init__(self, tag_sources, profiles=None, parent=None):
        super(MassTagEdit, self).__init__(parent)

        self.setWindowTitle(translate('Profile Config',
                                      'Configure Mass Tagging Profiles'))
        winsettings('masstag_edit', self)

        self.listbox = ListBox()
        self.tag_sources = tag_sources

        okcancel = OKCancel()
        okcancel.okButton.setDefault(True)

        self.buttonlist = ListButtons()

        connect = lambda control, signal, slot: getattr(control, signal).connect(slot)

        connect(okcancel, "ok", self.okClicked)
        connect(okcancel, "cancel", self.close)
        connect(self.buttonlist, "add", self.addClicked)
        connect(self.buttonlist, "edit", self.editClicked)
        connect(self.buttonlist, "moveup", self.moveUp)
        connect(self.buttonlist, "movedown", self.moveDown)
        connect(self.buttonlist, "remove", self.remove)
        connect(self.buttonlist, "duplicate", self.dupClicked)
        connect(self.listbox, "itemDoubleClicked", self.editClicked)
        connect(self.listbox, "currentRowChanged", self.enableListButtons)

        self.enableListButtons(self.listbox.currentRow())

        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel(translate('Profile Config',
                                          'Masstagging Profiles')))

        list_layout = QHBoxLayout()
        list_layout.addWidget(self.listbox, 1)
        list_layout.addLayout(self.buttonlist)

        layout.addLayout(list_layout)
        layout.addLayout(okcancel)
        if profiles is not None:
            self.setProfiles(profiles)

    def addClicked(self):
        win = MTProfileEdit(self.tag_sources, parent=self)
        win.setModal(True)
        win.profileChanged.connect(self.addProfile)
        win.show()

    def addProfile(self, profile):
        row = self.listbox.count()
        self.listbox.addItem(profile.name)
        self._profiles.append(profile)

    def dupClicked(self):
        row = self.listbox.currentRow()
        if row == -1:
            return
        win = MTProfileEdit(self.tag_sources, deepcopy(self._profiles[row]), self)
        win.setModal(True)
        win.profileChanged.connect(self.addProfile)
        win.show()

    def editClicked(self, item=None):
        if item:
            row = self.listbox.row(item)
        else:
            row = self.listbox.currentRow()

        if row == -1:
            return
        win = MTProfileEdit(self.tag_sources, self._profiles[row], self)
        win.setModal(True)
        win.profileChanged.connect(partial(self.replaceProfile, row))
        win.show()

    def enableListButtons(self, val):
        if val == -1:
            [button.setEnabled(False) for button in self.buttonlist.widgets[1:]]
        else:
            [button.setEnabled(True) for button in self.buttonlist.widgets[1:]]

    def loadProfiles(self, dirpath=PROFILEDIR):
        profiles = load_all_mtps(dirpath, self.tag_sources)
        self.setProfiles([_f for _f in profiles if _f])

    def moveDown(self):
        self.listbox.moveDown(self._profiles)

    def moveUp(self):
        self.listbox.moveUp(self._profiles)

    def okClicked(self):
        self.profilesChanged.emit(self._profiles)
        self.saveProfiles(PROFILEDIR, self._profiles)
        self.close()

    def remove(self):
        row = self.listbox.currentRow()
        if row == -1:
            return
        del (self._profiles[row])
        self.listbox.takeItem(row)

    def replaceProfile(self, row, profile):
        self._profiles[row] = profile
        self.listbox.item(row).setText(profile.name)

    def saveProfiles(self, dirpath, profiles):
        filenames = {}
        order = []
        for profile in profiles:
            filename = profile.name + '.mtp'
            i = 0
            while filename in filenames:
                filename = '%s_%d%s' % (profile.name, i, '.mtp')
                i += 1
            filenames[filename] = profile
            order.append(profile.name)
        files = glob.glob(os.path.join(dirpath, '*.mtp'))
        for f in files:
            if f not in filenames:
                try:
                    os.remove(f)
                except EnvironmentError:
                    pass
        for filename, profile in filenames.items():
            save_mtp(profile, os.path.join(dirpath, filename))
        f = open(os.path.join(dirpath, 'order'), 'w')
        f.write('\n'.join(order))
        f.close()

    def setProfiles(self, profiles):
        self._profiles = profiles
        for profile in self._profiles:
            self.listbox.addItem(profile.name)


class MTProfileEdit(QDialog):
    profileChanged = pyqtSignal(MassTagProfile, name='profileChanged')

    def __init__(self, tag_sources, profile=None, parent=None):
        super(MTProfileEdit, self).__init__(parent)

        self.setWindowTitle(translate('Profile Editor', 'Edit Masstagging Profile'))
        winsettings('masstag_profile', self)
        self._configs = []
        self.tag_sources = tag_sources
        self._tsps = []

        self._name = QLineEdit(translate('Profile Editor',
                                         'Masstagging Profile'))

        self._desc = QLineEdit()

        self.listbox = ListBox()

        self.okcancel = OKCancel()
        self.okcancel.okButton.setDefault(True)

        self.buttonlist = ListButtons()

        self.pattern = QLineEdit('%artist% - %album%/%track% - %title%')
        self.pattern.setToolTip(translate('Profile Editor',
                                          "<p>If no tag information is found in a file, "
                                          "the tags retrieved using this pattern will be used instead.</p>"))

        self.albumBound = QSpinBox()
        self.albumBound.setRange(0, 100)
        self.albumBound.setValue(70)
        self.albumBound.setToolTip(translate('Profile Editor',
                                             "<p>The artist and album fields will be used in "
                                             "determining whether an album matches the retrieved one. "
                                             "Each field will be compared using a fuzzy matching algorithm. "
                                             "If the resulting average match percentage is greater "
                                             "or equal than what you specify here it'll be "
                                             "considered to match.</p>"))

        self.matchFields = QLineEdit('artist, title')
        self.matchFields.setToolTip(translate('Profile Editor',
                                              '<p>The fields listed here will be used in '
                                              'determining whether a file matches a retrieved track. '
                                              'Each field will be compared using a fuzzy matching '
                                              'algorithm. If the resulting average match '
                                              'percentage is greater than the "Minimum Percentage" '
                                              'it\'ll be considered to match.</p>'))

        self.trackBound = QSpinBox()
        self.trackBound.setRange(0, 100)
        self.trackBound.setValue(80)

        self.jfdi = QCheckBox(translate('Profile Editor',
                                        'Brute force unmatched files.'))
        self.jfdi.setToolTip(translate('Profile Editor',
                                       "<p>Check to enable brute forcing matches. "
                                       " If a proper match isn't found for a file, "
                                       'the files will get sorted by filename, '
                                       'the retrieved tag sources by filename and '
                                       'corresponding (unmatched) tracks will matched.</p>'))

        self.existing = QCheckBox(translate('Profile Editor',
                                            'Update empty fields only.'))

        self.grid = QGridLayout()
        self.setLayout(self.grid)

        self.grid.addLayout(create_buddy(
            translate('Profile Editor', '&Name:'), self._name), 0, 0, 1, 2)
        self.grid.addLayout(create_buddy(
            translate('Profile Editor', '&Description'), self._desc), 1, 0, 1, 2)
        self.grid.addWidget(self.listbox, 2, 0)
        self.grid.setRowStretch(2, 1)
        self.grid.addLayout(self.buttonlist, 2, 1)
        self.grid.addLayout(create_buddy(translate('Profile Editor',
                                                   'Pattern to match filenames against.'),
                                         self.pattern, QVBoxLayout()), 3, 0, 1, 2)
        self.grid.addLayout(create_buddy(translate('Profile Editor',
                                                   'Minimum percentage required for album matches.'),
                                         self.albumBound), 4, 0, 1, 2)
        self.grid.addLayout(create_buddy(translate('Profile Editor',
                                                   'Match tracks using fields: '),
                                         self.matchFields, QVBoxLayout()), 5, 0, 1, 2)
        self.grid.addLayout(create_buddy(translate('Profile Editor',
                                                   'Minimum percentage required for track match.'),
                                         self.trackBound), 6, 0, 1, 2)
        self.grid.addWidget(self.jfdi, 7, 0, 1, 2)
        self.grid.addWidget(self.existing, 8, 0, 1, 2)
        self.grid.addLayout(self.okcancel, 9, 0, 1, 2)

        connect = lambda control, signal, slot: getattr(control, signal).connect(slot)

        connect(self.okcancel, "ok", self.okClicked)
        connect(self.okcancel, "cancel", self.close)
        connect(self.buttonlist, "add", self.addClicked)
        connect(self.buttonlist, "edit", self.editClicked)
        connect(self.buttonlist, "moveup", self.moveUp)
        connect(self.buttonlist, "movedown", self.moveDown)
        connect(self.buttonlist, "remove", self.remove)
        connect(self.buttonlist, "duplicate", self.dupClicked)
        connect(self.listbox, "itemDoubleClicked", self.editClicked)
        connect(self.listbox, "currentRowChanged", self.enableListButtons)

        if profile is not None:
            self.setProfile(profile)
        self.enableListButtons(self.listbox.currentRow())

    def addClicked(self):
        win = TSProfileEdit(self.tag_sources, None, self)
        win.setModal(True)
        win.profileChanged.connect(self.addTSProfile)
        win.show()

    def addTSProfile(self, profile):
        row = self.listbox.count()
        self.listbox.addItem(profile.tag_source.name)
        self._tsps.append(profile)

    def dupClicked(self):
        row = self.listbox.currentRow()
        if row == -1:
            return
        win = TSProfileEdit(self.tag_sources, self._tsps[row], self)
        win.setModal(True)
        win.profileChanged.connect(self.addTSProfile)
        win.show()

    def editClicked(self, item=None):
        if item:
            row = self.listbox.row(item)
        else:
            row = self.listbox.currentRow()

        if row == -1:
            return
        win = TSProfileEdit(self.tag_sources, self._tsps[row], self)
        win.setModal(True)
        win.profileChanged.connect(partial(self.replaceTSProfile, row))
        win.show()

    def replaceTSProfile(self, row, profile):
        self._tsps[row] = profile
        self.listbox.item(row).setText(profile.tag_source.name)

    def enableListButtons(self, val):
        if val == -1:
            [button.setEnabled(False) for button in self.buttonlist.widgets[1:]]
        else:
            [button.setEnabled(True) for button in self.buttonlist.widgets[1:]]

    def moveDown(self):
        self.listbox.moveDown(self._tsps)

    def moveUp(self):
        self.listbox.moveUp(self._tsps)

    def okClicked(self):
        fields = [z.strip() for z in
                  str(self.matchFields.text()).split(',')]

        mtp = MassTagProfile(str(self._name.text()),
                             str(self._desc.text()), fields, None,
                             str(self.pattern.text()), self._tsps,
                             self.albumBound.value() / 100.0,
                             self.trackBound.value() / 100.0, self.jfdi.isChecked(),
                             self.existing.isChecked(), '')

        self.profileChanged.emit(mtp)
        self.close()

    def remove(self):
        row = self.listbox.currentRow()
        if row == -1:
            return
        del (self._tsps[row])
        self.listbox.takeItem(row)

    def setProfile(self, profile):
        self._tsps = [tsp for tsp in profile.profiles if tsp.tag_source]
        [self.listbox.addItem(tsp.tag_source.name) for tsp in self._tsps]
        self.albumBound.setValue(profile.album_bound * 100)
        self.pattern.setText(profile.file_pattern)
        self.matchFields.setText(', '.join(profile.fields))
        self.trackBound.setValue(profile.track_bound * 100)
        self.jfdi.setChecked(profile.jfdi)
        self._name.setText(profile.name)
        self._desc.setText(profile.desc)
        self.existing.setChecked(profile.leave_existing)


class TSProfileEdit(QDialog):
    profileChanged = pyqtSignal(TagSourceProfile, name='profileChanged')

    def __init__(self, tag_sources, profile=None, parent=None):
        super(TSProfileEdit, self).__init__(parent)
        self.setWindowTitle(translate('Profile Editor',
                                      'Edit Tag Source Config'))
        winsettings('ts_profile_edit', self)
        self.tag_sources = tag_sources

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.fields = QLineEdit(self)
        layout.addLayout(
            create_buddy(translate('Defaults', 'Fields: '), self.fields))
        self.fields.setToolTip(translate('Profile Editor',
                                         '<p>Enter a comma-seperated list of fields to retrieve. '
                                         'Leave empty to retrieve all available fields/values. '

                                         '<br /><br />Eg. <b>artist, album, title</b> will '
                                         'only retrieve the artist, album and title fields of '
                                         'from the Tag Source. '

                                         '<br /><br />Start the list with '
                                         'the tilde (~) character to write all retrieved fields '
                                         ', but the ones listed. Eg the field list '
                                         '<b>~composer,__image</b> will write all fields but the '
                                         'composer and __image (aka cover art) fields.</p>'

                                         '<p>If a field has been retrieved in a previous '
                                         'Tag Source the values will be combined if they differ. '
                                         'Eg. If genre=<b>Rock</b> for the first tag source polled '
                                         'and genre=<b>Alternative</b> for the tag source '
                                         'polled second then the resulting field will have '
                                         'multiple-values ie. genre=<b>Rock\\\\Rap</b>'))

        self.replace_fields = QLineEdit(self)
        layout.addLayout(create_buddy(translate('Profile Editor',
                                                'Fields to replace: '), self.replace_fields))
        self.replace_fields.setToolTip(translate('Profile Editor',
                                                 'Enter a comma-separated lists of fields that\'ll replace any '
                                                 'retrieved from previously polled tag sources. '

                                                 '<br />Start the list with the tilde (~) character to replace all '
                                                 'but the fields you list. <br />'
                                                 '<b>NB: Fields listed here must also be listed in the '
                                                 'list of fields to retrieve.</b>'

                                                 '<br /><br />Eg. Assume you have two Tag Sources. '
                                                 'The first retrieves <b>artist=Freshlyground, '
                                                 'album=Nomvula, genre=Afro Pop</b>. The second source gets '
                                                 '<b>artist=Freshly Ground, album=Nomvula, '
                                                 'genre=Pop</b>. '
                                                 'For the second Tag Source, setting just <b>artist</b> as the '
                                                 'list of fields to replace will overwrite the artist '
                                                 'field retrieved from the first tag source. '
                                                 'The resulting retrieved fields/values as shown in puddletag will '
                                                 'then be <b>artist=Freshly Ground, album=Nomvula, '
                                                 'genre=Afro Pop\\\\Pop</b>.'))

        self.source = QComboBox()
        self.source.addItems([source.name for source in tag_sources])
        layout.addLayout(create_buddy(
            translate('Profile Editor', '&Source'), self.source))

        self.no_match = QComboBox()
        self.no_match.addItems(NO_MATCH_OPTIONS)
        layout.addLayout(create_buddy(translate('Profile Editor',
                                                '&If no results found: '), self.no_match))
        self.no_match.setToolTip(translate('Profile Editor',
                                           '<p><b>Continue</b>: The lookup for the current album will continue '
                                           'by checking the other tag sources if no matching results '
                                           'were found for this tag source.</p>'

                                           '<p><b>Stop:</b> The lookup for the current album will '
                                           'stop and any previously retrieved results will be used.</p>'))

        okcancel = OKCancel()
        okcancel.ok.connect(self._okClicked)
        okcancel.cancel.connect(self.close)
        layout.addLayout(okcancel)

        layout.addStretch()
        self.setMaximumHeight(layout.sizeHint().height())

        if profile:
            self.setProfile(profile)

    def _okClicked(self):
        source = self.tag_sources[self.source.currentIndex()]
        no_result = self.no_match.currentIndex()
        fields = fields_from_text(str(self.fields.text()))
        replace_fields = fields_from_text(str(self.replace_fields.text()))

        profile = TagSourceProfile(None, source, fields, no_result,
                                   replace_fields)

        self.close()
        self.profileChanged.emit(profile)

    def setProfile(self, profile):
        source_index = self.source.findText(profile.tag_source.name)
        if source_index != -1:
            self.source.setCurrentIndex(source_index)
        self.no_match.setCurrentIndex(profile.if_no_result)
        self.fields.setText(', '.join(profile.fields))
        self.replace_fields.setText(', '.join(profile.replace_fields))


class MassTagWindow(QWidget):
    setpreview = pyqtSignal(dict, name='setpreview')
    clearpreview = pyqtSignal(name='clearpreview')
    enable_preview_mode = pyqtSignal(name='enable_preview_mode')
    writepreview = pyqtSignal(name='writepreview')
    disable_preview_mode = pyqtSignal(name='disable_preview_mode')

    def __init__(self, parent=None, status=None):
        super(MassTagWindow, self).__init__(parent)
        self.receives = []
        self.emits = ['setpreview', 'clearpreview', 'enable_preview_mode',
                      'writepreview', 'disable_preview_mode']
        self.__flag = MassTagFlag()
        self.__flag.stop = False

        self.setWindowTitle(translate('Masstagging', 'Mass Tagging'))
        winsettings('masstaglog', self)
        self._startButton = QPushButton(translate('Masstagging', '&Search'))
        configure = QPushButton(translate('Masstagging', '&Configure Profiles'))
        write = QPushButton(translate('Masstagging', '&Write Previews'))
        clear = QPushButton(translate('Masstagging', 'Clear &Preview'))
        self._log = QTextEdit()
        self.tag_sources = status['initialized_tagsources']

        self.profileCombo = QComboBox()
        self.profile = None

        self._status = status

        status_obj.statusChanged.connect(self._appendLog)
        status_obj.logappend.connect(self._appendLog)
        self.profileCombo.currentIndexChanged.connect(self.changeProfile)
        self._startButton.clicked.connect(self.lookup)
        configure.clicked.connect(self.configure)
        write.clicked.connect(self.writePreview)
        clear.clicked.connect(self.clearPreview)

        buttons = QHBoxLayout()
        buttons.addWidget(configure)
        buttons.addStretch()
        buttons.addWidget(write)
        buttons.addWidget(clear)

        combo = QHBoxLayout()
        label = QLabel(translate('Masstagging', '&Profile:'))
        label.setBuddy(self.profileCombo)
        combo.addWidget(label)
        combo.addWidget(self.profileCombo, 1)
        combo.addWidget(self._startButton)

        layout = QVBoxLayout()
        layout.addLayout(combo)
        layout.addWidget(self._log)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _appendLog(self, text):
        mutex.lock()
        if not isinstance(text, str):
            text = str(text, 'utf8', 'replace')
        if text.startswith(':insert'):
            text = text[len(':insert'):]
            pos = len(self._log.toPlainText()) - 1
            pos = 0 if pos < 0 else pos
            self._log.textCursor().setPosition(pos)
            self._log.insertHtml(text)
        else:
            pos = len(self._log.toPlainText())
            if pos < 0:
                pos = 0
            self._log.textCursor().setPosition(pos)
            self._log.append(text)
        mutex.unlock()

    def changeProfile(self, index):
        try:
            self.profile = self.profiles[index]
        except IndexError:
            return
        cparser = PuddleConfig()
        cparser.set('masstagging', 'lastindex', index)

    def clearPreview(self):
        self.disable_preview_mode.emit()

    def configure(self):
        win = MassTagEdit(self.tag_sources, self.profiles, self)
        win.setModal(True)
        win.profilesChanged.connect(self.setProfiles)
        win.show()

    def lookup(self):
        button = self.sender()
        if self._startButton.text() != translate('Masstagging', '&Stop'):
            self.__flag.stop = False
            self._log.clear()
            self._startButton.setText(translate('Masstagging', '&Stop'))
            self._start()
        else:
            self._startButton.setText(translate('Masstagging', '&Search'))
            self.__flag.stop = True

    def loadSettings(self):
        convert_mtps(PROFILEDIR)
        if not os.path.exists(PROFILEDIR):
            os.mkdir(PROFILEDIR)
        self.setProfiles(load_all_mtps(PROFILEDIR, self.tag_sources))
        index = PuddleConfig().get('masstagging', 'lastindex', 0)
        if index < self.profileCombo.count():
            self.profileCombo.setCurrentIndex(index)

    def setProfiles(self, profiles):
        self.profiles = profiles
        if not profiles:
            self.profileCombo.clear()
            return
        self.profileCombo.currentIndexChanged.disconnect(self.changeProfile)
        old = self.profileCombo.currentText()
        self.profileCombo.clear()
        self.profileCombo.addItems([p.name for p in profiles])
        index = self.profileCombo.findText(old)
        if index == -1:
            index = 0
        self.profileCombo.setCurrentIndex(index)
        self.profile = profiles[index]

        if self.profile.desc:
            self.profileCombo.setToolTip(self.profile.desc)
        self.profileCombo.currentIndexChanged.connect(self.changeProfile)

    def _start(self):
        mtp = self.profile
        if self.profile == None:
            set_status(translate('Masstagging',
                                 '<b>Please choose a tagging profile.</b>'))
            self._startButton.setText(translate('Masstagging', '&Search'))
            return None

        tag_groups = split_files(self._status['selectedfiles'],
                                 mtp.file_pattern)

        search_msg = translate('Masstagging',
                               'An error occured during the search: <b>%s</b>')

        retrieve_msg = translate('Masstagging',
                                 'An error occured during album retrieval: <b>%s</b>')

        def search_error(error, mtp):
            thread.statusChanged.emit(search_msg % str(error))

        def retrieval_error(error, mtp):
            thread.statusChanged.emit(retrieve_msg % str(error))

        def run_masstag():
            replace_fields = []
            for files in tag_groups:
                mtp.clear()

                masstag(mtp, files, self.__flag, search_error,
                        retrieval_error)

                retrieved = merge_tsp_tracks(mtp.profiles)
                ret = match_files(files, retrieved,
                                  mtp.track_bound, mtp.fields,
                                  mtp.jfdi, mtp.leave_existing, True)[0]

                if ret:
                    thread.enable_preview_mode.emit()
                    thread.setpreview.emit(ret)

                set_status('<hr width="45%" /><br />')

        def finished(value):
            if not (value is True):
                set_status(translate('Masstagging',
                                     '<b>Lookups completed.</b>'))
            self._startButton.setText(translate('Masstagging', '&Search'))
            self.__flag.stop = False

        thread = PuddleThread(run_masstag, self)
        thread.setpreview.connect(self.setpreview)
        thread.enable_preview_mode.connect(self.enable_preview_mode)
        thread.threadfinished.connect(finished)
        thread.statusChanged.connect(set_status)

        thread.start()

    def writePreview(self):
        self.writepreview.emit()


control = ('Mass Tagging', MassTagWindow, RIGHTDOCK, False)

if __name__ == '__main__':
    app = QApplication([])
    from .. import puddletag, tagsources

    puddletag.load_plugins()
    sources = [z() for z in tagsources.tagsources]
    tsp = TagSourceProfile(None, sources[-1], ['field1', 'field2'],
                           1, ['repl1', 'repl2'])
    # win = TSProfileEdit(sources, tsp)
    mtp = MassTagProfile('Searching', 'Testing Search',
                         ['artist', 'title'], None, '%artist% - ktg',
                         [tsp], 0.70, 0.90, False, True,
                         {'album': ['(.*?)\s+\(.*\)', '$1']})
    # win = MTProfileEdit(sources, mtp)

    win = MassTagEdit(sources)
    win.loadProfiles()
    win.show()
    app.exec_()
