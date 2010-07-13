# -*- coding: utf-8 -*-

import pdb, os

from functools import partial
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import string

from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import (ListBox, ListButtons, PuddleConfig,
    OKCancel, winsettings)
import puddlestuff.resource
from puddlestuff.tagsources import amg, musicbrainz, freedb, amazon
from puddlestuff.util import split_by_tag
from puddlestuff.webdb import strip

import exampletagsource

pyqtRemoveInputHook()

NO_MATCH_OPTIONS = ['Continue', 'Stop']
SINGLE_MATCH_OPTIONS = ['Combine and continue', 'Replace and continue', 
    'Combine and Stop', 'Replace and Stop']
AMBIGIOUS_MATCH_OPTIONS = ['Use best match', 'Do nothing and continue',
    'Retry if match found in another tag source']
tagsources = [z.info[0]() for z in 
    [exampletagsource, amg, musicbrainz, freedb, amazon]]

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
    fields = filter(None, map(string.strip, text.split(',')))
    return fields

def load_config(filename = None):
    filename = os.path.join(os.path.expanduser('~',), 
        'Desktop/masstagging.conf')
    cparser = PuddleConfig(filename)
    name = cparser.get('info', 'name', '')
    numsources = cparser.get('info', 'numsources', 0)
    
    configs = []
    for num in range(numsources):
        section = 'config%s' % num
        get = lambda key, default: cparser.get(section, key, default)
        source = get('source', 'Musicbrainz')
        no = get('no_match', 0)
        single = get('single_match', 0)
        fields = fields_from_text(get('fields', ''))
        many = get('many_match', 0)
        configs.append([source, no, single, fields, many])

    return configs

def match_files(files, tracks):
    return zip(files, tracks)

def merge_info(oldinfo, newinfo):
    oldinfo.update(newinfo)

def merge_track(track1, track2):
    track1.update(track2)

def merge_tracks(tracks, newtracks):
    if tracks is None:
        return newtracks
    if newtracks is None:
        return tracks
    for track, newtrack in zip(tracks, newtracks):
        merge_track(track, newtrack)
    if len(newtracks) > len(tracks):
        tracks.extend(newtracks[len(tracks):])
    return tracks

#def merge_results

def retrieve(results):
    ret = []
    for tagsource, result, files, config in results:
        if not result:
            pass
        elif len(result) == 1:
            source_info, source_tracks = tagsource.retrieve(result[0][0])
            source_tracks = merge_tracks(result[0][1], source_tracks)
            ret.append((config[2], config[3], source_info, source_tracks))
        else:
            pass
    return ret

def search(configs, audios):
    tag_groups = split_by_tag(audios, 'album', 'artist')

    source_names = dict([(z.name, z) for z in 
        tagsources])

    for album, artists in tag_groups.items():
        files = []
        results = []
        [files.extend(z) for z in artists.values()]
        for config in configs:
            tagsource = source_names[config[0]]
            group = split_by_tag(files, *tagsource.group_by)
            result = tagsource.search(group.keys()[0], 
                group.values()[0].items()[0])
            if result:
                results.append([tagsource, result, files, config])
            elif not result:
                results.append([tagsource, [], files, config])
        yield results

def save_configs(name, configs):
    #filename = os.path.join(SAVEDIR, name + u'.conf')
    filename = os.path.join(os.path.expanduser('~',), 
        'Desktop/masstagging.conf')
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


class MassTagging(QDialog):
    def __init__(self, parent=None):
        super(MassTagging, self).__init__(parent)
        
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
        self._fields.setText(u', '.join(fields[1]))
        self._many_match.setCurrentIndex(no_match)

class Retriever(QDialog):
    def __init__(self, configs, parent=None):
        super(Retriever, self).__init__(parent)
        

if __name__ == '__main__':
    from puddlestuff import audioinfo
    import glob
    #app = QApplication([])
    previous = ('FreeDB', 1, 2, [True, ['artist', 'title']], 1)
    audios = [audioinfo.Tag(z) for z in 
        glob.glob('/mnt/variable/Music/Angie Stone - The Very Best Of/*.ogg')]
    configs = load_config()
    for result in search(configs, audios):
        print retrieve(result)
    #win = ConfigEdit(tagsources, previous)
    #win = MassTagging()
    #win.show()
    #app.exec_()