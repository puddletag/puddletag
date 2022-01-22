import glob
import logging
import os
import sys
import traceback
from copy import deepcopy

from PyQt5.QtCore import Qt, pyqtRemoveInputHook, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout, \
    QInputDialog, QLabel, QLineEdit, QPushButton, QSpinBox, QTextEdit, QToolButton, QVBoxLayout, \
    QWidget

from . import audioinfo, version_string
from .constants import (TEXT, COMBO, SPINBOX,
                        CHECKBOX, RIGHTDOCK, CONFIGDIR)
from .findfunc import FuncError
from .functions import replace_regex
from .puddleobjects import (create_buddy, winsettings,
                            ListBox, ListButtons, OKCancel, PuddleConfig, PuddleThread)
from .releasewidget import ReleaseWidget
from .tagsources import (tagsources, status_obj, set_useragent,
                         write_log, RetrievalError, mp3tag, SubmissionError)
from .util import (isempty, pprint_tag,
                   split_by_field, to_string, translate)

pyqtRemoveInputHook()

TAGSOURCE_CONFIG = os.path.join(CONFIGDIR, 'tagsources.conf')
MTAG_SOURCE_DIR = os.path.join(CONFIGDIR, 'mp3tag_sources')

DEFAULT_SEARCH_TIP = translate("WebDB",
                               "Enter search parameters here. If empty, the selected "
                               "files are used. <ul><li><b>artist;album</b> searches "
                               "for a specific album/artist combination.</li><li>To "
                               "list the albums by an artist leave off the album "
                               "part, but keep the semicolon (eg. <b>Ratatat;</b>). "
                               "For a album only leave the artist part as in "
                               "<b>;Resurrection.</li></ul>")

FIELDLIST_TIP = translate("WebDB",
                          'Enter a comma seperated list of fields to write. '
                          '<br /><br />Eg. <b>artist, album, title</b> will only '
                          'write the artist, album and title fields of the '
                          'retrieved tags. <br /><br />If you want to '
                          'exclude some fields, but write all others start the '
                          'list the tilde (~) character. Eg <b>~composer, '
                          '__image</b> will write all fields but the '
                          'composer and __image fields.')

DEFAULT_REGEXP = {'album': ['(.*?)([\(\[\{].*[\)\]\}])', '$1']}


def apply_regexps(audio, regexps=None):
    if regexps is None:
        regexps = DEFAULT_REGEXP
    audio = deepcopy(audio)
    changed = False
    for field, (regexp, output) in regexps.items():
        if field not in audio:
            continue
        text = to_string(audio[field])
        try:
            val = replace_regex(audio, text, regexp, output)
            if val:
                audio[field] = val
                if not changed and val != text:
                    changed = val
        except FuncError:
            continue
    return changed, audio


def display_tag(tag):
    """Used to display tags in in a human parseable format."""
    tag = dict((k, v) for k, v in tag.items() if
               not k.startswith('#') and not isempty(v))

    if not tag:
        return translate("WebDB", "<b>Nothing to display.</b>")
    fmt = "<b>%s</b>: %s<br />"
    text = pprint_tag(tag, fmt, True)
    if text.endswith('<br />'):
        text = text[:-len('<br />')]
    return text


def load_mp3tag_sources(dirpath=MTAG_SOURCE_DIR):
    "Loads Mp3tag tag sources from dirpath and return the tag source classes."
    files = glob.glob(os.path.join(dirpath, '*.src'))
    classes = []
    for f in files:
        try:
            idents, search, album = mp3tag.open_script(f)
            classes.append(mp3tag.Mp3TagSource(idents, search, album))
        except:
            logging.exception(translate("WebDB", "Couldn't load Mp3tag Tag Source %s") % f)
            continue
    return classes


def strip(audio, field_list, reverse=False, leave_exact=False):
    '''Returns dict of key/values from audio where the key is in field_list.

    If reverse is True then the dict will consist of all
    fields found in audio where the key is NOT IN in field_list.

    If the first field in field_list starts with '~' then reverse will be
    set to True.

    Any fields starting with '#' will be removed.
    '''
    if not field_list:
        ret = dict([(key, audio[key]) for key in audio if
                    not key.startswith('#')])
        if leave_exact and '#exact' in audio:
            ret['#exact'] = audio['#exact']
        return ret
    tags = field_list[::]
    if tags and tags[0].startswith('~'):
        reverse = True
        tags[0] = tags[0][1:]
    else:
        reverse = False
    if reverse:
        ret = dict([(key, audio[key]) for key in audio if key not in
                    tags and not key.startswith('#')])
    else:
        ret = dict([(key, audio[key]) for key in field_list
                    if not key.startswith('#') and key in audio])

    if leave_exact and '#exact' in audio:
        ret['#exact'] = audio['#exact']
    return ret


def split_strip(stringlist):
    '''Splits and strips each comma-delimited string in a list of strings.

    >>> split_strip(['artist, title', 'album,genre'])
    [['artist', 'title'], ['album', 'genre']]
    '''
    return [[field.strip() for field in s.split(',')] for s in stringlist]


class FieldsEdit(QWidget):
    fieldsChanged = pyqtSignal(list, name='fieldsChanged')

    def __init__(self, tags=None, parent=None):
        QWidget.__init__(self, parent)
        if not tags:
            tags = []
        label = QLabel()
        label.setText(translate("Defaults", '&Fields'))
        self._text = QLineEdit(', '.join(tags))
        label.setBuddy(self._text)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 0)
        layout.addWidget(self._text, 1)

        self._text.textChanged.connect(
            self.emitTags)

        self.setLayout(layout)

    def emitTags(self, text=None):
        self.fieldsChanged.emit(self.tags(text))

    def setTags(self, tags):
        self._text.setText(', '.join(tags))

    def setToolTip(self, value):
        QWidget.setToolTip(self, value)
        self._text.setToolTip(value)

    def tags(self, text=None):
        if not text:
            return [_f for _f in [z.strip() for z in
                                  str(self._text.text()).split(',')] if _f]
        else:
            return [_f for _f in [z.strip() for z in str(text).split(',')] if _f]


class SimpleDialog(QDialog):
    """Class for simple dialog creation."""
    editingFinished = pyqtSignal(list, name='editingFinished')

    def __init__(self, title, controls, parent=None):
        """title => Dialog's title.
        controls is a list of 3-element-lists.

        The three 3-element lists consist of:
            description => Descriptive label for the control.
            control_type => One of TEXT, COMBO, CHECKBOX corresponding
                to a QLineEdit, QComboBox and QCheckBox being created
                respectively.
            default => Default arguments.
                Can be any string for TEXT,
                Must be a list of strings for COMBO as these will form the
                    items selectable by the combo box.
                Can be either True or False for CheckBox.

        A dialog will be created with vertical layout. Like so:
            <label>
            <control>
            <label>
            <control>

        When the user has finished editing an 'editingFinished' signal
        will be emitted containing a list with the new value.

        The list will consist of the value for each control in the order
        given. For TEXT it'll a string. COMBO an integer corresponding to
        the selected index. True or False for CHECK.
        """

        QDialog.__init__(self, parent)
        vbox = QVBoxLayout()
        self._controls = []
        winsettings(title, self)
        self.setWindowTitle(translate("WebDB", 'Configure: %s') % title)
        for desc, ctype, default in controls:
            if ctype == TEXT:
                control = QLineEdit(default)
                vbox.addLayout(create_buddy(desc, control))
            elif ctype == COMBO:
                control = QComboBox()
                control.addItems(default[0])
                control.setCurrentIndex(default[1])
                label = QLabel(desc)
                label.setBuddy(control)
                vbox.addWidget(label)
                vbox.addWidget(control)
            elif ctype == CHECKBOX:
                control = QCheckBox(desc)
                if default:
                    control.setCheckState(Qt.Checked)
                else:
                    control.setCheckState(Qt.Unchecked)
                vbox.addWidget(control)
            elif ctype == SPINBOX:
                control = QSpinBox()
                control.setMinimum(default[0])
                control.setMaximum(default[1])
                control.setValue(default[2])
                vbox.addLayout(create_buddy(desc, control))

            self._controls.append(control)
        okcancel = OKCancel()
        okcancel.ok.connect(self.okClicked)
        okcancel.cancel.connect(self.close)
        vbox.addLayout(okcancel)
        vbox.addStretch()
        self.setLayout(vbox)

    def okClicked(self):
        values = []
        for control in self._controls:
            if isinstance(control, QLineEdit):
                values.append(str(control.text()))
            elif isinstance(control, QComboBox):
                values.append(control.currentIndex())
            elif isinstance(control, QCheckBox):
                values.append(control.isChecked())
            elif isinstance(control, QSpinBox):
                values.append(control.value())
        self.editingFinished.emit(values)
        self.close()


class SortOptionEditor(QDialog):
    options = pyqtSignal(list, name='options')

    def __init__(self, options, parent=None):
        """options is a list of strings. Each a comma-delimited field list.

        Eg. ['artist, title', 'album, genre']
        """

        QDialog.__init__(self, parent)
        connect = lambda c, signal, s: getattr(c, signal).connect(s)
        self.listbox = ListBox()
        self.listbox.setSelectionMode(self.listbox.ExtendedSelection)

        buttons = ListButtons()

        self.listbox.addItems(options)
        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox, 1)

        hbox.addLayout(buttons)

        okcancel = OKCancel()
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addLayout(okcancel)
        self.setLayout(vbox)

        connect(buttons, "add", self.addPattern)
        connect(buttons, "edit", self.editItem)
        buttons.duplicateButton.setVisible(False)
        okcancel.ok.connect(self.applySettings)
        okcancel.cancel.connect(self.applySettings)
        self.listbox.connectToListButtons(buttons)
        self.listbox.editButton = buttons.editButton
        connect(self.listbox, "itemDoubleClicked", self._doubleClicked)

    def addPattern(self):
        l = self.listbox.item
        patterns = [str(l(z).text()) for z in range(self.listbox.count())]
        row = self.listbox.currentRow()
        if row < 0:
            row = 0
        (text, ok) = QInputDialog().getItem(self, translate("WebDB",
                                                            'Add sort option'),
                                            translate("WebDB",
                                                      'Enter a sorting option (a comma-separated list of fields. '
                                                      'Eg. "artist, title")'), patterns, row)
        if ok:
            self.listbox.clearSelection()
            self.listbox.addItem(text)
            self.listbox.setCurrentRow(self.listbox.count() - 1)

    def _doubleClicked(self, item):
        self.editItem()

    def editItem(self, row=None):
        if row is None:
            row = self.listbox.currentRow()
        l = self.listbox.item
        patterns = [str(l(z).text()) for z in range(self.listbox.count())]
        (text, ok) = QInputDialog().getItem(self,
                                            translate("WebDB", 'Edit sort option'),
                                            translate("WebDB",
                                                      'Enter a sorting option (a comma-separated list of fields. '
                                                      'Eg. "artist, title")'), patterns, row)
        if ok:
            item = l(row)
            item.setText(text)
            item.setSelected(True)

    def applySettings(self):
        item = self.listbox.item
        options = [str(item(row).text())
                   for row in range(self.listbox.count())]
        self.close()
        self.options.emit(options)


class SettingsDialog(QWidget):
    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        self.title = translate('Settings', 'Tag Sources')

        label = QLabel(translate("WebDB",
                                 '&Display format for individual tracks.'))
        self._text = QLineEdit()
        label.setBuddy(self._text)

        albumlabel = QLabel(translate("WebDB",
                                      'Display format for &retrieved albums'))
        self._albumdisp = QLineEdit()
        albumlabel.setBuddy(self._albumdisp)

        sortlabel = QLabel(translate("WebDB",
                                     'Sort retrieved albums using order:'))
        self._sortoptions = QComboBox()
        sortlabel.setBuddy(self._sortoptions)
        editoptions = QPushButton(translate("Defaults", '&Edit'))
        editoptions.clicked.connect(self._editOptions)

        ua_label = QLabel(translate("WebDB",
                                    'User-Agent to when accessing web sites.'))
        self._ua = QTextEdit()

        self.jfdi = QCheckBox(translate('Profile Editor',
                                        'Brute force unmatched files.'))
        self.jfdi.setToolTip(translate('Profile Editor',
                                       "<p>If a proper match isn't found for a file, the files "
                                       "will get sorted by filename, the retrieved tag sources "
                                       "by filename and corresponding (unmatched) tracks will "
                                       "matched.</p>"))

        self.matchFields = QLineEdit('artist, title')
        self.matchFields.setToolTip(translate('Profile Editor',
                                              "<p>The fields listed here will be used in determining "
                                              "whether a track matches the retrieved track. Each "
                                              "field will be compared using a fuzzy matching algorithm. "
                                              "If the resulting average match percentage is greater "
                                              'than the "Minimum Percentage" it\'ll be considered to '
                                              "match.</p>"))

        self.albumBound = QSpinBox()
        self.albumBound.setToolTip(translate('Profile Editor',
                                             "<p>The artist and album fields will be used in "
                                             "determining whether an album matches the retrieved one. "
                                             "Each field will be compared using a fuzzy matching "
                                             "algorithm. If the resulting average match percentage "
                                             "is greater or equal than what you specify here "
                                             "it'll be considered to match.</p>"))

        self.albumBound.setRange(0, 100)
        self.albumBound.setValue(70)

        self.trackBound = QSpinBox()
        self.trackBound.setRange(0, 100)
        self.trackBound.setValue(80)

        vbox = QVBoxLayout()
        vbox.addWidget(label)
        vbox.addWidget(self._text)

        vbox.addWidget(albumlabel)
        vbox.addWidget(self._albumdisp)

        vbox.addWidget(sortlabel)
        sortbox = QHBoxLayout()
        sortbox.addWidget(self._sortoptions, 1)
        sortbox.addWidget(editoptions)
        vbox.addLayout(sortbox)

        vbox.addWidget(ua_label)
        vbox.addWidget(self._ua)

        frame = QGroupBox(translate(
            'WebDB', 'Automatic retrieval options'))

        auto_box = QVBoxLayout()
        frame.setLayout(auto_box)

        auto_box.addLayout(create_buddy(translate('Profile Editor',
                                                  'Minimum &percentage required for album matches.'),
                                        self.albumBound))
        auto_box.addLayout(create_buddy(translate('Profile Editor',
                                                  'Match tracks using &fields: '), self.matchFields))
        auto_box.addLayout(create_buddy(translate('Profile Editor',
                                                  'Minimum percentage required for track match.'),
                                        self.trackBound))
        auto_box.addWidget(self.jfdi)

        vbox.addWidget(frame)

        vbox.addStretch()
        self.setLayout(vbox)
        self.loadSettings()

    def applySettings(self, control):
        listbox = control.listbox
        text = str(self._text.text())
        listbox.trackPattern = text

        albumdisp = str(self._albumdisp.text())
        listbox.albumPattern = albumdisp

        sort_combo = self._sortoptions
        sort_options_text = [str(sort_combo.itemText(i)) for i in
                             range(sort_combo.count())]
        sort_options = split_strip(sort_options_text)
        listbox.setSortOptions(sort_options)

        listbox.sort(sort_options[sort_combo.currentIndex()])

        useragent = str(self._ua.toPlainText())
        set_useragent(useragent)

        listbox.jfdi = self.jfdi.isChecked()
        listbox.matchFields = [z.strip() for z in
                               str(self.matchFields.text()).split(',')]
        listbox.albumBound = self.albumBound.value() / 100.0
        listbox.trackBound = self.trackBound.value() / 100.0

        cparser = PuddleConfig(os.path.join(CONFIGDIR, 'tagsources.conf'))
        set_value = lambda s, v: cparser.set('tagsources', s, v)
        set_value('trackpattern', text)
        set_value('albumpattern', albumdisp)
        set_value('sortoptions', sort_options_text)
        set_value('useragent', useragent)
        set_value('album_bound', self.albumBound.value())
        set_value('track_bound', self.trackBound.value())
        set_value('jfdi', listbox.jfdi)
        set_value('match_fields', listbox.matchFields)

    def loadSettings(self):
        cparser = PuddleConfig(os.path.join(CONFIGDIR, 'tagsources.conf'))

        trackpattern = cparser.get('tagsources', 'trackpattern',
                                   '%track% - %title%')

        self._text.setText(trackpattern)

        sortoptions = cparser.get('tagsources', 'sortoptions',
                                  ['artist, album', 'album, artist'])
        self._sortoptions.clear()
        self._sortoptions.addItems(sortoptions)

        albumformat = cparser.get('tagsources', 'albumpattern',
                                  '%artist% - %album% $if(%__numtracks%, [%__numtracks%], "")')
        self._albumdisp.setText(albumformat)

        self._ua.setText(cparser.get('tagsources',
                                     'useragent', 'puddletag/' + version_string))

        self.albumBound.setValue(
            cparser.get('tagsources', 'album_bound', 70, True))
        self.trackBound.setValue(
            cparser.get('tagsources', 'track_bound', 80, True))
        self.jfdi.setChecked(
            bool(cparser.get('tagsources', 'jfdi', True, True)))

        fields = cparser.get('tagsources', 'match_fields',
                             ['artist', 'title'])
        fields = ', '.join(z.strip() for z in fields)
        self.matchFields.setText(fields)

    def _editOptions(self):
        text = self._sortoptions.itemText
        win = SortOptionEditor([text(i) for i in
                                range(self._sortoptions.count())], self)
        win.options.connect(self._setSortOptions)
        win.setModal(True)
        win.show()

    def _setSortOptions(self, items):
        current = self._sortoptions.currentText()
        self._sortoptions.clear()
        self._sortoptions.addItems(items)
        index = self._sortoptions.findText(current)
        if index == -1:
            index = 0
        self._sortoptions.setCurrentIndex(index)


def load_source_prefs(name, preferences):
    cparser = PuddleConfig(TAGSOURCE_CONFIG)
    ret = []
    for option in preferences:
        if option[1] == COMBO:
            ret.append(cparser.get(name, option[0], option[2][1]))
        elif option[1] == SPINBOX:
            ret.append(cparser.get(name, option[0], option[2][2]))
        else:
            ret.append(cparser.get(name, option[0], option[2]))
    return ret


def tag_source_search(ts, group, files):
    """Helper method for tag source searches."""

    if not ts.group_by:
        return ts.search(files), files

    ret = []

    for primary in group:
        albums = ts.search(primary, group[primary])
        if albums:
            ret.extend(albums)
            continue

        audio = {'album': primary}
        changed, audio = apply_regexps(audio)
        if changed:
            audio['album'] = audio['album'].strip()
            write_log(translate('WebDB', 'Retrying search with %s') %
                      audio['album'])
            ret.extend(ts.search(audio['album'], group[primary]))

    return ret, files


class MainWin(QWidget):
    writepreview = pyqtSignal(name='writepreview')
    setpreview = pyqtSignal(object, name='setpreview')
    clearpreview = pyqtSignal(name='clearpreview')
    enable_preview_mode = pyqtSignal(name='enable_preview_mode')
    logappend = pyqtSignal(str, name='logappend')
    disable_preview_mode = pyqtSignal(name='disable_preview_mode')

    def __init__(self, status, parent=None):
        QWidget.__init__(self, parent)
        self.settingsdialog = SettingsDialog

        connect = lambda obj, sig, slot: getattr(obj, sig).connect(slot)

        self.setWindowTitle("Tag Sources")

        self.receives = []
        self.emits = ['writepreview', 'setpreview', 'clearpreview',
                      'enable_preview_mode', 'logappend', 'disable_preview_mode']

        self.fieldMapping = audioinfo.mapping

        self._status = status
        self.__sources = [z() for z in tagsources]
        self.__sources.extend(load_mp3tag_sources())

        for ts in self.__sources:
            if hasattr(ts, 'preferences') and not isinstance(ts, QWidget):
                try:
                    ts.applyPrefs(load_source_prefs(ts.name, ts.preferences))
                except:
                    continue

        status['initialized_tagsources'] = self.__sources

        self.curSource = self.__sources[0]
        self.__sourceFields = [[] for z in self.__sources]

        self.sourcelist = QComboBox()
        self.sourcelist.addItems([ts.name for ts in self.__sources])
        connect(self.sourcelist, 'currentIndexChanged', self.changeSource)

        sourcelabel = QLabel(translate("WebDB", 'Sour&ce: '))
        sourcelabel.setBuddy(self.sourcelist)

        preferences = QToolButton()
        preferences.setIcon(QIcon(':/preferences.png'))
        preferences.setToolTip(translate("WebDB", 'Configure'))
        self.__preferencesButton = preferences
        connect(preferences, 'clicked', self.configure)

        self.searchEdit = QLineEdit()
        self.searchEdit.setToolTip(DEFAULT_SEARCH_TIP)
        connect(self.searchEdit, 'returnPressed', self.search)

        self.searchButton = QPushButton(translate("WebDB", "&Search"))
        self.searchButton.setDefault(True)
        self.searchButton.setAutoDefault(True)
        connect(self.searchButton, "clicked", self.search)

        self.submitButton = QPushButton(translate("WebDB",
                                                  "S&ubmit Tags"))
        connect(self.submitButton, "clicked", self.submit)

        write_preview = QPushButton(translate("WebDB", '&Write'))
        connect(write_preview, "clicked", self.writePreview)

        clear = QPushButton(translate("Previews", "Clea&r preview"))
        connect(clear, "clicked",
                lambda: self.disable_preview_mode.emit())

        self.label = QLabel(translate("WebDB",
                                      "Select files and click on Search to retrieve metadata."))
        connect(status_obj, 'statusChanged', self.label.setText)

        self.listbox = ReleaseWidget(status, self.curSource)
        self.__updateEmpty = QCheckBox(translate("WebDB",
                                                 'Update empty fields only.'))
        connect(self.listbox, 'statusChanged', self.label.setText)
        connect(self.listbox, 'preview', self.emit_preview)
        connect(self.listbox, 'exactMatches', self.emitExact)

        self.__autoRetrieve = QCheckBox(translate("WebDB",
                                                  'Automatically retrieve matches.'))

        self.__fieldsEdit = FieldsEdit()
        self.__fieldsEdit.setToolTip(FIELDLIST_TIP)
        connect(self.__fieldsEdit, 'fieldsChanged', self.__changeFields)

        infolabel = QLabel()
        infolabel.setOpenExternalLinks(True)
        connect(self.listbox, 'infoChanged', infolabel.setText)

        connect(status_obj, 'logappend', self.logappend)

        sourcebox = QHBoxLayout()
        sourcebox.addWidget(sourcelabel)
        sourcebox.addWidget(self.sourcelist, 1)
        sourcebox.addWidget(preferences)

        hbox = QHBoxLayout()
        hbox.addWidget(self.searchButton, 0)
        hbox.addWidget(self.searchEdit, 1)

        vbox = QVBoxLayout()
        vbox.addLayout(sourcebox)
        vbox.addLayout(hbox)

        vbox.addWidget(self.label)
        vbox.addWidget(self.listbox, 1)
        hbox = QHBoxLayout()
        hbox.addWidget(infolabel, 1)
        hbox.addStretch()
        hbox.addWidget(self.submitButton)
        hbox.addWidget(write_preview)
        hbox.addWidget(clear)
        vbox.addLayout(hbox)

        vbox.addWidget(self.__fieldsEdit)
        vbox.addWidget(self.__updateEmpty)
        vbox.addWidget(self.__autoRetrieve)
        self.setLayout(vbox)
        self.changeSource(0)

    def _applyPrefs(self, prefs):
        self.curSource.applyPrefs(prefs)
        cparser = PuddleConfig(TAGSOURCE_CONFIG)
        name = self.curSource.name
        for section, value in zip(self.curSource.preferences, prefs):
            cparser.set(name, section[0], value)

    def __changeFields(self, fields):
        self.listbox.tagsToWrite = fields
        self.__sourceFields[self.sourcelist.currentIndex()] = fields

    def changeSource(self, index):
        self.curSource = self.__sources[index]
        self.searchEdit.setToolTip(
            getattr(self.curSource, 'tooltip', DEFAULT_SEARCH_TIP))
        self.listbox.tagSource = self.curSource

        self.__preferencesButton.setVisible(
            not (getattr(self.curSource, 'preferences', False) is False))

        self.__fieldsEdit.setTags(self.__sourceFields[index])

        self.listbox.setMapping(self.fieldMapping.get(self.curSource.name, {}))

        self.searchEdit.setEnabled(hasattr(self.curSource, 'keyword_search'))

        self.submitButton.setVisible(hasattr(self.curSource, 'submit'))

    def configure(self):
        config = getattr(self.curSource, 'preferences', None)
        if config is None:
            return

        if isinstance(config, QWidget):
            win = config(parent=self)
        else:
            defaults = load_source_prefs(self.curSource.name, config)
            prefs = deepcopy(config)
            for pref, value in zip(prefs, defaults):
                if pref[1] == SPINBOX:
                    try:
                        pref[2][2] = int(value)
                    except ValueError:
                        pass
                elif pref[1] == COMBO:
                    pref[2][1] = value
                else:
                    pref[2] = value
            win = SimpleDialog(self.curSource.name, prefs, self)
        win.setModal(True)
        win.editingFinished.connect(self._applyPrefs)
        win.show()

    def emit_preview(self, tags):
        if not self.__updateEmpty.isChecked():
            self.enable_preview_mode.emit()
            self.setpreview.emit(tags)
        else:
            files = self._status['selectedfiles']
            previews = []
            for f, r in zip(files, tags):
                temp = {}
                for field in r:
                    if field not in f:
                        temp[field] = r[field]
                previews.append(temp)
            self.enable_preview_mode.emit()
            self.setpreview.emit(previews)

    def emitExact(self, d):
        if not self.__updateEmpty.isChecked():
            self.enable_preview_mode.emit()
            self.setpreview.emit(d)
        else:
            previews = []
            for f, r in d.items():
                temp = {}
                for field in r:
                    if field not in f:
                        temp[field] = r[field]
                previews.append(temp)
            self.enable_preview_mode.emit()
            self.setpreview.emit(previews)

    def loadSettings(self):
        settings = PuddleConfig(os.path.join(CONFIGDIR, 'tagsources.conf'))
        get = lambda s, k, i=False: settings.get('tagsources', s, k, i)

        source = get('lastsource', 'Musicbrainz')
        self.__sourceFields = [settings.get('tagsourcetags', ts.name, [])
                               for ts in self.__sources]

        index = self.sourcelist.findText(source)
        if index == -1:
            index = 0
        self.sourcelist.setCurrentIndex(index)
        self.__fieldsEdit.setTags(self.__sourceFields[index])
        df = get('trackpattern', '%track% - %title%')
        self.listbox.trackPattern = df

        albumformat = get('albumpattern',
                          '%artist% - %album%$if(%__numtracks%, [%__numtracks%], "")')
        self.listbox.albumPattern = albumformat

        sort_options = get('sortoptions',
                           ['artist, album', 'album, artist'])
        sort_options = split_strip(sort_options)
        self.listbox.setSortOptions(sort_options)

        sortindex = get('lastsort', 0)
        self.listbox.sort(sort_options[sortindex])

        filepath = os.path.join(CONFIGDIR, 'mappings')
        self.setMapping(audioinfo.loadmapping(filepath))

        useragent = get('useragent', '')
        if useragent:
            set_useragent(useragent)

        checkstate = get('existing', False)
        self.__updateEmpty.setChecked(checkstate)

        checkstate = get('autoretrieve', False)
        self.__autoRetrieve.setChecked(checkstate)

        self.listbox.albumBound = get('album_bound', 70, True) / 100.0
        self.listbox.trackBound = get('track_bound', 80, True) / 100.0
        self.listbox.jfdi = bool(get('jfdi', True, True))
        self.listbox.matchFields = get('match_fields', ['artist', 'title'])

    def setResults(self, retval):
        self.searchButton.setEnabled(True)
        if isinstance(retval, (str, str, str)):
            self.label.setText(retval)
        else:
            releases, files = retval
            if releases:
                self.label.setText(translate("WebDB",
                                             'Searching complete.'))
            else:
                self.label.setText(translate("WebDB",
                                             'No matching albums were found.'))
            if files and self.__autoRetrieve.isChecked():
                self.listbox.setReleases(releases, files)
            else:
                self.listbox.setReleases(releases)
            self.listbox.infoChanged.emit('')

    def search(self):
        if not self.searchButton.isEnabled():
            return
        files = self._status['selectedfiles']
        if self.curSource.group_by:
            group = split_by_field(files, *self.curSource.group_by)
        self.label.setText(translate("WebDB", 'Searching...'))
        text = None
        if self.searchEdit.text() and self.searchEdit.isEnabled():
            text = str(self.searchEdit.text())
        elif not files:
            self.label.setText(translate("WebDB",
                                         '<b>Select some files or enter search paramaters.</b>'))
            return

        def search():
            try:
                ret = []
                if text:
                    return self.curSource.keyword_search(text), None
                else:
                    return tag_source_search(self.curSource, group, files)
            except RetrievalError as e:
                return translate('WebDB',
                                 'An error occured: %1').arg(str(e))
            except Exception as e:
                traceback.print_exc()
                return translate('WebDB',
                                 'An unhandled error occurred: %1').arg(str(e))

        self.searchButton.setEnabled(False)
        t = PuddleThread(search, self)
        t.threadfinished.connect(self.setResults)
        t.start()

    def submit(self):
        files = self._status['selectedfiles']
        self.submitButton.setEnabled(False)

        def end(text):
            self.submitButton.setEnabled(True)
            self.label.setText(text)

        def submit():
            try:
                self.curSource.submit(files)
            except SubmissionError as e:
                traceback.print_exc()
                return translate('WebDB',
                                 'An error occured: %1').arg(str(e))
            except Exception as e:
                traceback.print_exc()
                return translate('WebDB',
                                 'An unhandled error occurred: %1').arg(str(e))

            return translate("WebDB", "Submission completed.")

        t = PuddleThread(submit, self)
        t.threadfinished.connect(end)
        t.start()

    def saveSettings(self):
        settings = PuddleConfig()
        settings.filename = os.path.join(CONFIGDIR, 'tagsources.conf')
        settings.set('tagsources', 'lastsource', self.sourcelist.currentText())
        for i, ts in enumerate(self.__sources):
            settings.set('tagsourcetags', ts.name, self.__sourceFields[i])
        settings.set('tagsources', 'lastsort', self.listbox.lastSortIndex)
        settings.set('tagsources', 'existing', self.__updateEmpty.isChecked())
        settings.set('tagsources', 'autoretrieve',
                     self.__autoRetrieve.isChecked())

    def setMapping(self, mapping):
        self.fieldMapping = mapping
        if self.curSource.name in mapping:
            self.listbox.setMapping(mapping[self.curSource.name])
        else:
            self.listbox.setMapping({})

    def writePreview(self):
        self.writepreview.emit()
        self.label.setText(translate("WebDB", "<b>Tags were written.</b>"))


control = ('Tag Sources', MainWin, RIGHTDOCK, False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    status = {}
    status['selectedfiles'] = exampletags.tags
    win = MainWin(status)
    win.show()
    app.exec_()
