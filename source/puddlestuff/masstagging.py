# -*- coding: utf-8 -*-

import pdb, os

from functools import partial
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import string

from puddlestuff.constants import SAVEDIR, RIGHTDOCK
from puddlestuff.puddleobjects import (ListBox, ListButtons, OKCancel, 
    PuddleConfig, PuddleThread, ratio, winsettings)
import puddlestuff.resource
from puddlestuff.tagsources import RetrievalError, status_obj, set_status
from puddlestuff.util import split_by_tag, to_string
from puddlestuff.webdb import strip

#import exampletagsource, qltagsource

pyqtRemoveInputHook()

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

#tagsources = [z.info[0]() for z in 
    #[exampletagsource, qltagsource, amg, musicbrainz, freedb, amazon]]
#tagsources = [z.info[0]() for z in tagsources]

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

def create_buddy(text, control):
    label = QLabel(text)
    label.setBuddy(control)

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
    name = cparser.get('info', 'name', '')
    numsources = cparser.get('info', 'numsources', 0)
    
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

    return configs

def match_files(files, tracks, minimum = 0.7):
    with_tracknums = filter(lambda f: u'track' in f, files)
    source_tracknums = filter(lambda f: u'track' in f, tracks)

    if len(with_tracknums) == len(files) == len(source_tracknums):
        tracks = dict([(track['track'][0], track) for track in tracks])
        return dict([(f, tracks[f['track'][0]]) for f in files if 
            f['track'][0] in tracks])
    else:
        source_tracknums = dict([(track['track'][0], track) for 
            track in source_tracknums])
        ret = dict([(f, tracks[f['track'][0]]) for f in with_tracknums if 
            f['track'][0] in with_tracknums])
        keys = ['artist', 'title']
        for f in files:
            scores = {}
            for track in tracks:
                totals = [ratio(f.get(key, [u'a'])[0].lower(), 
                    track.get(key, [u'b'])[0].lower()) 
                    for key in keys]
                scores[min(totals)] = track
            max_ratio = max(scores)
            if max_ratio > minimum and f not in ret:
                ret[f] = scores[max_ratio]
        return ret

def merge_tracks(old_tracks, newtracks):
    if not old_tracks:
        return newtracks
    if not newtracks:
        return old_tracks

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

def retrieve(results):
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
                matches = find_best(matches, files)
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
        ret.append(dict([(key, list(set(value))) for 
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

def search(tagsources, configs, audios):
    set_status('<b>Initializing...</b>')
    tag_groups = split_by_tag(audios, 'album', 'artist')

    source_names = dict([(z.name, z) for z in 
        tagsources])

    for album, artists in tag_groups.items():
        if len(artists) == 1:
            artist = to_string(artists.keys()[0])
        else:
            artist = u'Various Artists'
        set_status(u'<br />Starting search for: <b>%s - %s</b>' % (artist, album))
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
    
    cparser.set('info', 'name', name)
    cparser.set('info', 'numsources', len(configs))
    
    for num, config in enumerate(configs):
        section = 'config%s' % num
        cparser.set(section, 'source', config[0])
        cparser.set(section, 'no_match', config[1])
        cparser.set(section, 'single_match', config[2])
        cparser.set(section, 'fields', u','.join(config[3]))
        cparser.set(section, 'many_match', config[4])

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

        self.grid.addWidget(self.listbox,0, 0)
        self.grid.setRowStretch(0, 1)
        self.grid.addLayout(self.buttonlist, 0,1)
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

        self.grid.addLayout(self.okcancel,1,0,1,2)
        
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
        save_configs('masstagging', self._configs)
        self.emit(SIGNAL('configsChanged'), self._configs)
        self.close()
    
    def remove(self):
        row = self.listbox.currentRow()
        if row == -1:
            return
        del(self._configs[row])
        self.listbox.takeItem(row)
    
    def _setConfigs(self, configs):
        self._configs = configs
        [self.listbox.addItem(config_str(config)) for config in configs]

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
        print (source, no_match, single_match, fields, many_matches)
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
        def method():
            try:
                for result in search(self.tagsources, self._configs, files):
                    if not self.wasCanceled:
                        try:
                            matched = match_files(*retrieve(result))
                            thread.emit(SIGNAL('setpreview'), matched)
                        except RetrievalError:
                            pass
            except RetrievalError:
                return
        thread = PuddleThread(method)
        self.connect(thread, SIGNAL('setpreview'), SIGNAL('setpreview'))
        thread.start()
        while thread.isRunning():
            QApplication.processEvents()
    
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