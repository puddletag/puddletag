# -*- coding: utf-8 -*-

import pdb, os

from functools import partial
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import string

from puddlestuff.constants import SAVEDIR, RIGHTDOCK
from puddlestuff.findfunc import filenametotag
from puddlestuff.puddleobjects import (ListBox, ListButtons, OKCancel, 
    PuddleConfig, PuddleThread, ratio, winsettings)
import puddlestuff.resource
from puddlestuff.tagsources import RetrievalError, status_obj, set_status
from puddlestuff.util import split_by_tag, to_string
from puddlestuff.webdb import strip

#import exampletagsource, qltagsource

#pyqtRemoveInputHook()

CONFIG = os.path.join(SAVEDIR, 'masstagging.conf')

NO_MATCH_OPTIONS = ['Continue', 'Stop']
SINGLE_MATCH_OPTIONS = ['Combine and continue', 'Replace and continue', 
    'Combine and stop', 'Replace and stop']
AMBIGIOUS_MATCH_OPTIONS = ['Use best match', 'Do nothing and continue']

COMBINE_CONTINUE = 0
REPLACE_CONTINUE = 1
COMBINE_STOP = 2
REPLACE_STOP = 3

CONTINUE = 0
STOP = 1

USE_BEST = 0
DO_NOTHING = 1
RETRY = 2

ALBUM_BOUND = 'album'
TRACK_BOUND = 'track'
PATTERN = 'pattern'
SOURCE_CONFIGS = 'source_configs'
FIELDS = 'fields'

def to_list(value):
    if isinstance(value, (str, int, long)):
        value = [unicode(value)]
    elif isinstance(value, unicode):
        value = [value]
    return value

def combine(fields, info, retrieved, old_tracks):
    new_tracks = []
    for track in retrieved:
        info_copy = info.copy()
        info_copy.update(track)
        new_tracks.append(strip(info_copy, fields))
    return merge_tracks(old_tracks, new_tracks)

def config_str(config):
    return config[0]

def create_buddy(text, control, hbox=None):
    label = QLabel(text)
    label.setBuddy(control)

    if not hbox:
        hbox = QHBoxLayout()
    hbox.addWidget(label)
    hbox.addWidget(control, 1)
    
    return hbox

def fields_from_text(text):
    if not text:
        return []
    return filter(None, map(string.strip, text.split(u',')))

def find_best(matches, files, minimum=0.7):
    group = split_by_tag(files, 'album', 'artist')
    album = group.keys()[0]
    artists = group[album].keys()
    if len(artists) == 1:
        artist = artists[0]
    else:
        artist = u'Various Artists'
    d = {'artist': artist, 'album': album}
    scores = {}

    for match in matches:
        info = match[0]
        totals = [ratio(d[key].lower(), to_string(info[key]).lower()) 
            for key in d if key in info]
        if len(totals) == len(d):
            scores[min(totals)] = match
    
    max_ratio = max(scores)
    if max_ratio > minimum:
        return [scores[max_ratio]]

def load_config(filename = CONFIG):
    cparser = PuddleConfig(filename)
    info_section = 'info'
    name = cparser.get(info_section, 'name', '')
    numsources = cparser.get(info_section, 'numsources', 0)
    album_bound = cparser.get(info_section, ALBUM_BOUND, 70)
    track_bound = cparser.get(info_section, TRACK_BOUND, 80)
    match_fields = cparser.get(info_section, FIELDS, ['artist', 'title'])
    pattern = cparser.get(info_section, PATTERN, 
        '%artist% - %album%/%track% - %title%')
    
    configs = []
    for num in range(numsources):
        section = 'config%s' % num
        get = lambda key, default: cparser.get(section, key, default)
        source = get('source', 'MusicBrainz')
        no = get('no_match', 0)
        single = get('single_match', 0)
        fields = fields_from_text(get('fields', ''))
        many = get('many_match', 0)
        configs.append([source, no, single, fields, many])

    return {SOURCE_CONFIGS: configs, PATTERN: pattern, 
        ALBUM_BOUND: album_bound, TRACK_BOUND: track_bound,
        FIELDS: match_fields}

def match_files(files, tracks, minimum = 0.7, keys = None):
    if not keys:
        keys = ['artist', 'title']
    ret = {}
    for f in files:
        scores = {}
        for track in tracks:
            totals = [ratio(to_list(f.get(key, u'a'))[0].lower(), 
                to_list(track.get(key, u'b'))[0].lower()) 
                for key in keys]
            scores[min(totals)] = track
        if scores:
            max_ratio = max(scores)
            if max_ratio > minimum and f['__file'] not in ret:
                ret[f['__file']] = scores[max_ratio]
    return ret

def merge_tracks(old_tracks, new_tracks):
    if not old_tracks:
        return new_tracks
    if not new_tracks:
        return old_tracks
    
    sort_func = lambda track: to_string(track['track']) if 'track' in \
        track else to_string(track.get('title', u''))
        
    old_tracks = sorted(old_tracks, key=sort_func)
    new_tracks = sorted(new_tracks, key=sort_func)

    for old, new in zip(old_tracks, new_tracks):
        for key in old.keys() + new.keys():
            if key in new and key in old:
                old[key] = to_list(old[key])
                old[key].extend(to_list(new[key]))
            elif key in new:
                old[key] = to_list(new[key])
    if len(new_tracks) > len(old_tracks):
        old_tracks.extend(new_tracks[len(old_tracks):])
    return old_tracks

def retrieve(results, album_bound = 0.7):
    tracks = []
    info = {}
    for tagsource, matches, files, config in results:
        fields = config[3]
        if not matches:
            operation = config[1]
            if operation == CONTINUE:
                set_status('<b>%s</b>: No matches, trying other sources.' % 
                    tagsource.name)
                continue
            elif operation == STOP:
                set_status('<b>%s</b>: No matches, stopping retrieval.' % 
                    tagsource.name)
                break
        elif len(matches) > 1:
            operation = config[4]
            if operation == DO_NOTHING:
                set_status('<b>%s</b>: Inexact matches found, doing nothing.' % 
                    tagsource.name)
                continue
            elif operation == USE_BEST:
                set_status('<b>%s</b>: Inexact matches found, using best.' % 
                    tagsource.name)
                matches = find_best(matches, files, album_bound)
                if not matches:
                    set_status('<b>%s</b>: No match found within bounds.' % 
                    tagsource.name)
                    continue

        if len(matches) == 1:
            set_status('<b>%s</b>: Retrieving album.' % 
                    tagsource.name)
            stop, tracks, source_info = parse_single_match(matches, tagsource, 
                config[2], fields, tracks)
            info.update(source_info)
            if stop:
                set_status('<b>%s</b>: Stopping.' % 
                    tagsource.name)
                break
    ret = []
    for track in tracks:
        ret.append(dict([(key, remove_dupes(value)) for 
            key, value in track.items()]))
    return files, ret

def replace(fields, info, retrieved, old_tracks):
    new_tracks = []
    for track in retrieved:
        info_copy = info.copy()
        info_copy.update(track)
        new_tracks.append(strip(info_copy, fields))
    if len(retrieved) > len(old_tracks):
        old_tracks = new_tracks[len(old_tracks):]
    [old.update(new) for old, new in zip(old_tracks, new_tracks)]
    return old_tracks

def remove_dupes(value):
    value = to_list(value)
    try:
        value = list(set(value))
    except TypeError:
        'Unhashable type like dictionary for pictures.'
    return value

def parse_single_match(matches, tagsource, operation, fields, tracks):
    source_info, source_tracks = tagsource.retrieve(matches[0][0])
    source_tracks = merge_tracks(matches[0][1], source_tracks)
    stop = False
    if operation == COMBINE_CONTINUE:
        tracks = combine(fields, source_info, source_tracks, tracks)
    elif operation == COMBINE_STOP:
        tracks = combine(fields, source_info, source_tracks, tracks)
        stop = True
    elif operation == REPLACE_CONTINUE:
        tracks = replace(fields, source_info, source_tracks, tracks)
    elif operation == REPLACE_STOP:
        tracks = replace(fields, source_info, source_tracks, tracks)
        stop = True
    return stop, tracks, source_info

def insert_status(msg):
    set_status(u':insert%s' % msg)

def search(tagsources, configs, audios, 
    pattern = '%dummy% - %album%/%artist% - %track% - %title%'):

    set_status('<b>Initializing...</b>')
    tag_groups = split_files(audios, pattern)

    source_names = dict([(z.name, z) for z in 
        tagsources])

    for group in tag_groups:
        album_groups = split_by_tag(group, 'album', 'artist').items()
        if len(album_groups) == 1:
            album, artists = album_groups[0]
        else:
            [tag_groups.extend(z[1].values()) for z in album_groups]
            continue
        if len(artists) == 1:
            artist = to_string(artists.keys()[0])
        else:
            artist = u'Various Artists'
        set_status(u'<br />Starting search for: <b>%s - %s</b>' % (
            artist, album))
        files = []
        results = []
        [files.extend(z) for z in artists.values()]
        for config in configs:
            tagsource = source_names[config[0]]
            set_status(u'Polling <b>%s<b>: ' % config[0])
            group = split_by_tag(files, *tagsource.group_by)
            field = group.keys()[0]
            result = tagsource.search(field, group[field])
            if result:
                results.append([tagsource, result, files, config])
                if len(result) == 1:
                    insert_status(u'Exact match found.')
                else:
                    insert_status(u'%s albums found.' % len(result))
            elif not result:
                results.append([tagsource, [], files, config])
                insert_status(u'No albums found')
        yield results

def save_configs(name, configs, filename=CONFIG):
    cparser = PuddleConfig(filename)
    info_section = 'info'
    
    cparser.set(info_section, 'name', name)
    for key in [ALBUM_BOUND, PATTERN, TRACK_BOUND, FIELDS]:
        cparser.set(info_section, key, configs[key])
    
    cparser.set(info_section, 'numsources', len(configs[SOURCE_CONFIGS]))
    
    for num, config in enumerate(configs[SOURCE_CONFIGS]):
        section = 'config%s' % num
        cparser.set(section, 'source', config[0])
        cparser.set(section, 'no_match', config[1])
        cparser.set(section, 'single_match', config[2])
        cparser.set(section, 'fields', u','.join(config[3]))
        cparser.set(section, 'many_match', config[4])

def split_files(audios, pattern):
    dir_groups = split_by_tag(audios, '__dirpath', None)
    tag_groups = []

    for dirpath, files in dir_groups.items():
        tags = []
        for f in files:
            if pattern:
                tag = filenametotag(pattern, f.filepath, True)
                if tag:
                    tag.update(f.tags.copy())
                else:
                    tag = f.tags.copy()
            else:
                tag = f.tags.copy()
            tag['__file'] = f
            tags.append(tag)
        tag_groups.append(tags)
    return tag_groups

class MassTagConfig(QDialog):
    def __init__(self, tagsources, parent=None):
        super(MassTagConfig, self).__init__(parent)
        
        self.setWindowTitle('Mass Tagging')
        winsettings('masstagging', self)
        self._configs = []
        self.tagsources = tagsources
        
        self.listbox = ListBox()

        self.okcancel = OKCancel()
        self.okcancel.ok.setDefault(True)
        self.grid = QGridLayout()

        self.buttonlist = ListButtons()
        
        self.pattern = QLineEdit()
        
        self.albumBound = QSpinBox()
        self.albumBound.setRange(0,100)
        self.albumBound.setValue(70)
        
        self.matchFields = QLineEdit('artist, title')
        self.trackBound = QSpinBox()
        self.trackBound.setRange(0,100)
        self.trackBound.setValue(80)

        self.grid.addWidget(self.listbox,0, 0)
        self.grid.setRowStretch(0, 1)
        self.grid.addLayout(self.buttonlist, 0, 1)
        self.grid.addLayout(create_buddy('Pattern to match filenames against.',
            self.pattern, QVBoxLayout()), 1, 0, 1, 2)
        self.grid.addLayout(create_buddy('Minimum percentage required for '
            'best matches.', self.albumBound), 2, 0, 1, 2)
        self.grid.addLayout(create_buddy('Match tracks using fields: ',
            self.matchFields, QVBoxLayout()), 3, 0, 1, 2)
        self.grid.addLayout(create_buddy('Minimum percentage required for '
            'track match.', self.trackBound), 4, 0, 1, 2)
        
        self.setLayout(self.grid)
        
        connect = lambda control, signal, slot: self.connect(
            control, SIGNAL(signal), slot)

        connect(self.okcancel, "ok" , self.okClicked)
        connect(self.okcancel, "cancel",self.close)
        connect(self.buttonlist, "add", self.addClicked)
        connect(self.buttonlist, "edit", self.editClicked)
        connect(self.buttonlist, "moveup", self.moveUp)
        connect(self.buttonlist, "movedown", self.moveDown)
        connect(self.buttonlist, "remove", self.remove)
        connect(self.buttonlist, "duplicate", self.dupClicked)
        connect(self.listbox, "itemDoubleClicked (QListWidgetItem *)",
            self.editClicked)
        connect(self.listbox, "currentRowChanged(int)", self.enableListButtons)

        self.grid.addLayout(self.okcancel,5,0,1,2)

        self._setConfigs(load_config())
        self.enableListButtons(self.listbox.currentRow())

    def addClicked(self):
        win = ConfigEdit(self.tagsources, None, self)
        win.setModal(True)
        self.connect(win, SIGNAL('sourceChanged'), self._addSource)
        win.show()
    
    def _addSource(self, *source):
        row = self.listbox.count()
        self.listbox.addItem(config_str(source))
        self._configs.append(source)
    
    def dupClicked(self):
        row = self.listbox.currentRow()
        if row == -1:
            return
        win = ConfigEdit(self.tagsources, self._configs[row], self)
        win.setModal(True)
        self.connect(win, SIGNAL('sourceChanged'), self._addSource)
        win.show()
    
    def editClicked(self, item=None):
        if item:
            row = self.listbox.row(item)
        else:
            row = self.listbox.currentRow()
        
        if row == -1:
            return
        win = ConfigEdit(self.tagsources, self._configs[row], self)
        win.setModal(True)
        self.connect(win, SIGNAL('sourceChanged'), 
            partial(self._editSource, row))
        win.show()
    
    def _editSource(self, row, *source):
        self._configs[row] = source
        self.listbox.item(row).setText(config_str(source))
    
    def enableListButtons(self, val):
        if val == -1:
            [button.setEnabled(False) for button in self.buttonlist.widgets[1:]]
        else:
            [button.setEnabled(True) for button in self.buttonlist.widgets[1:]]
    
    def moveDown(self):
        self.listbox.moveDown(self._configs)
    
    def moveUp(self):
        self.listbox.moveUp(self._configs)
    
    def okClicked(self):
        fields = [z.strip() for z in 
            unicode(self.matchFields.text()).split(',')]
        configs = {
            SOURCE_CONFIGS: self._configs,
            PATTERN: unicode(self.pattern.text()),
            ALBUM_BOUND: self.albumBound.value(),
            TRACK_BOUND: self.trackBound.value(),
            FIELDS: fields}
        save_configs('masstagging', configs)
        self.emit(SIGNAL('configsChanged'), configs)
        self.close()
    
    def remove(self):
        row = self.listbox.currentRow()
        if row == -1:
            return
        del(self._configs[row])
        self.listbox.takeItem(row)
    
    def _setConfigs(self, configs):
        self._configs = configs[SOURCE_CONFIGS]
        [self.listbox.addItem(config_str(config)) for config 
            in self._configs]
        self.albumBound.setValue(configs[ALBUM_BOUND])
        self.pattern.setText(configs[PATTERN])
        self.matchFields.setText(u', '.join(configs[FIELDS]))
        self.trackBound.setValue(configs[TRACK_BOUND])

class ConfigEdit(QDialog):
    def __init__(self, tagsources, previous=None, parent=None):
        super(ConfigEdit, self).__init__(parent)
        self.setWindowTitle('Edit Config')
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self._source = QComboBox()
        self._source.addItems([source.name for source in tagsources])
        layout.addLayout(create_buddy('&Source', self._source))
        
        self._no_match = QComboBox()
        self._no_match.addItems(NO_MATCH_OPTIONS)
        layout.addLayout(create_buddy('&If no matches found:', self._no_match))
        
        self._single_match = QComboBox()
        self._single_match.addItems(SINGLE_MATCH_OPTIONS)
        layout.addLayout(create_buddy('&If single match found:', 
            self._single_match))
        
        self._fields = QLineEdit()
        tooltip = 'Enter a comma seperated list of fields to write. <br /><br />Eg. <b>artist, album, title</b> will only write the artist, album and title fields of the retrieved tags. <br /><br />If you want to exclude some fields, but write all others start the list the tilde (~) character. Eg <b>~composer, __image</b> will write all fields but the composer and __image fields.'
        self._fields.setToolTip(tooltip)
        layout.addLayout(create_buddy('Fields:', self._fields))
        
        self._many_match = QComboBox()
        self._many_match.addItems(AMBIGIOUS_MATCH_OPTIONS)
        layout.addLayout(create_buddy('&If ambiguous matches found:', 
            self._many_match))
        
        okcancel = OKCancel()
        self.connect(okcancel, SIGNAL('ok'), self._okClicked)
        self.connect(okcancel, SIGNAL('cancel'), self.close)
        layout.addLayout(okcancel)
        
        layout.addStretch()
        
        if previous:
            self._setConfig(*previous)
    
    def _okClicked(self):
        source = unicode(self._source.currentText())
        no_match = self._no_match.currentIndex()
        single_match = self._single_match.currentIndex()
        many_matches = self._many_match.currentIndex()
        fields = fields_from_text(unicode(self._fields.text()))
        #print (source, no_match, single_match, fields, many_matches)
        self.close()
        self.emit(SIGNAL('sourceChanged'), source, no_match, single_match, 
            fields, many_matches)
    
    def _setConfig(self, source_name, no_match, single, fields, many):
        source_index = self._source.findText(source_name)
        if source_index != -1:
            self._source.setCurrentIndex(source_index)
        self._no_match.setCurrentIndex(no_match)
        self._single_match.setCurrentIndex(single)
        self._fields.setText(u', '.join(fields))
        self._many_match.setCurrentIndex(no_match)

class Retriever(QWidget):
    def __init__(self, parent=None, status=None):
        super(Retriever, self).__init__(parent)
        self.receives = []
        self.emits = ['setpreview', 'clearpreview']
        self.wasCanceled = False
        
        self.setWindowTitle('Mass Tagging')
        winsettings('masstaglog', self)
        start = QPushButton('&Start')
        configure = QPushButton('&Configure')
        write = QPushButton('&Write')
        clear = QPushButton('Clear &Preview')
        self._log = QTextEdit()
        self.tagsources = status['initialized_tagsources']
        #[self.tagsources.append(z.info[0]()) for z 
            #in [exampletagsource, qltagsource]]
        self._status = status

        self.connect(status_obj, SIGNAL('statusChanged'), self._appendLog)
        self.connect(status_obj, SIGNAL('logappend'), self._appendLog)
        
        self.connect(start, SIGNAL('clicked()'), self.lookup)
        self.connect(configure, SIGNAL('clicked()'), self.configure)
        self.connect(write, SIGNAL('clicked()'), self.writePreview)
        self.connect(clear, SIGNAL('clicked()'), self.clearPreview)
        
        buttons = QHBoxLayout()
        buttons.addWidget(start)
        buttons.addWidget(configure)
        buttons.addStretch()
        buttons.addWidget(write)
        buttons.addWidget(clear)
        
        layout = QVBoxLayout()
        layout.addLayout(buttons)
        layout.addWidget(self._log)
        self.setLayout(layout)

        self._configs = load_config()
    
    def _appendLog(self, text):
        if text.startswith(u':insert'):
            text = text[len(u':insert'):]
            self._log.textCursor().setPosition(len(self._log.toPlainText()))
            self._log.insertHtml(text)
        else:
            self._log.append(text)
    
    def clearPreview(self):
        self.emit(SIGNAL('clearpreview'))
    
    def configure(self):
        win = MassTagConfig(self.tagsources, self)
        win.setModal(True)
        self.connect(win, SIGNAL('configsChanged'), self._setConfigs)
        win.show()
    
    def lookup(self):
        button = self.sender()
        if button.text() != '&Stop':
            self.wasCanceled = False
            self._log.clear()
            button.setText('&Stop')
            self._start()
            button.setText('&Start')
        else:
            button.setText('&Start')
            self.wasCanceled = True
    
    def _setConfigs(self, configs):
        self._configs = configs
    
    def _start(self):
        files = self._status['selectedfiles']
        source_configs = self._configs[SOURCE_CONFIGS]
        pattern = self._configs[PATTERN]
        album_bound = self._configs[ALBUM_BOUND] / 100.0
        track_bound = self._configs[TRACK_BOUND] / 100.0
        track_fields = self._configs[FIELDS]
        def method():
            try:
                results = search(self.tagsources, source_configs, 
                    files, pattern)
                for result in results:
                    if not self.wasCanceled:
                        try:
                            retrieved = retrieve(result, album_bound)
                            matched = match_files(retrieved[0], retrieved[1], 
                                track_bound, track_fields)
                            thread.emit(SIGNAL('setpreview'), matched)
                        except RetrievalError, e:
                            self._appendLog(u'<b>Error: %s</b>' % unicode(e))
            except RetrievalError:
                return
        
        def finished(value):
            self._appendLog('<b>Lookup completed.</b>')
        
        thread = PuddleThread(method, self)
        self.connect(thread, SIGNAL('setpreview'), SIGNAL('setpreview'))
        self.connect(thread, SIGNAL('threadfinished'), finished)

        thread.start()
    
    def writePreview(self):
        self.emit(SIGNAL('writepreview'))
        

control = ('Mass Tagging', Retriever, RIGHTDOCK, False)

if __name__ == '__main__':
    from puddlestuff import audioinfo
    
    import time
    #previous = ('FreeDB', 1, 2, [True, ['artist', 'title']], 1)
    
    app = QApplication([])
    #win = ConfigEdit(tagsources, previous)
    #win = MassTagging()
    win = Retriever(tagsources)
    win.show()
    app.exec_()