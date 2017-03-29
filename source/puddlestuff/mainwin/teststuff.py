# -*- coding: utf-8 -*-
import sys, os
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from puddlestuff.constants import RIGHTDOCK
from puddlestuff.puddleobjects import PuddleThread, natcasecmp, PuddleDock
from puddlestuff import audioinfo
import pdb
from puddlestuff.audioinfo.util import (strlength, strbitrate, strfrequency, usertags, PATH,
                  getfilename, lnglength, getinfo, FILENAME, INFOTAGS,
                  READONLY, isempty, FILETAGS, EXTENSION, DIRPATH,
                  getdeco, setdeco, str_filesize)
from itertools import imap
ATTRIBUTES = ('frequency', 'length', 'bitrate', 'accessed', 'size', 'created',
              'modified')
import tags

class Tag(audioinfo.MockTag):
    """Use as base for all tag classes."""
    IMAGETAGS = ()
    mapping = {}
    revmapping = {}

    _hash = {PATH: 'filepath',
             FILENAME:'filename',
             EXTENSION: 'ext',
             DIRPATH: 'dirpath'}
    
    def __init__(self, dictionary = None):
        #self.IMAGETAGS = tuple(set([IMAGETAGS[random.randint(0,3)] for z in IMAGETAGS]))
        self.IMAGETAGS = ()
        self.images = []
        #if audioinfo.DATA not in self.IMAGETAGS:
            #self.IMAGETAGS = (,)
        #else:
            #images = set([random.randint(0, 11) for z in xrange(11)])
            #self.images = [self.image(**{'data': pictures[i],
                        #'imagetype': random.randint(0,21),
                        #'description': unicode(i)}) for i in images]

        if dictionary:
            self.link(dictionary)
        
        self._set_attrs(ATTRIBUTES)

    def link(self, dictionary):
        self._tags = dictionary
        self.filepath = dictionary['__filename']

    def save(self):
        logging.info('saving ' + self.filename)

    def copy(self):
        return Tag(self._tags.copy())

    @getdeco
    def __getitem__(self,key):
        """Get the tag value from self._tags. There is a slight
        caveat in that this method will never return a KeyError exception.
        Rather it'll return ''."""
        if key == '__image':
            return self.images

        try:
            return self._tags[key]
        except KeyError:
            #This is a bit of a bother since there will never be a KeyError exception
            #But its needed for the sort method in tagmodel.TagModel, .i.e it fails
            #if a key doesn't exist.
            return ""

    @setdeco
    def __setitem__(self,key,value):
        if key in READONLY:
            return
        elif key in FILETAGS:
            setattr(self, self._hash[key], value)
            return

        if key not in INFOTAGS and isempty(value):
            del(self[key])
        elif key in INFOTAGS or isinstance(key, (int, long)):
            self._tags[key] = value
        elif (key not in INFOTAGS) and isinstance(value, (basestring, int, long)):
            self._tags[key.lower()] = [unicode(value)]
        else:
            self._tags[key.lower()] = [unicode(z) for z in value]

    def mutvalues(self):
        #Retrieves key, value pairs according to id3.
        return [self._tags[key] for key in self if type(key) is not int and not key.startswith('__')]


class TestWidget(QWidget):
    def __init__(self, parent=None, status = None):
        QWidget.__init__(self, parent)
        self.emits = ['setpreview']
        self.receives = []
        button = QPushButton('Set Previews')
        self.connect(button, SIGNAL('clicked()'), self._changePreview)
        self._status = status
        
        load1000button = QPushButton('Load 1000')
        self.connect(load1000button, SIGNAL('clicked()'), self._load1000)
        self._status = status
        
        save_tags = QPushButton('Save Files')
        self.connect(save_tags, SIGNAL('clicked()'), self._saveTags)
        self._status = status
        
        load_many = QPushButton('Load Many')
        self.connect(load_many, SIGNAL('clicked()'), self._loadMany)
        self._status = status

        box = QVBoxLayout()
        box.addWidget(button)
        box.addWidget(load1000button)
        box.addWidget(save_tags)
        box.addWidget(load_many)
        self.setLayout(box)

    def _changePreview(self):
        status = self._status
        files = status['allfiles'][2:10]
        d = {}
        for f in files:
            d[f] = {'artist': 'Preview Artist', 'title': 'Preview Title'}
        self.emit(SIGNAL('setpreview'), d)
    
    def _load1000(self):
        table = PuddleDock._controls['table']
        table.model().load(map(Tag, tags.tags))
        table.model().saveModification = False
    
    def _loadMany(self):
        model = PuddleDock._controls['table'].model()
        num, ok = QInputDialog.getInt(self, 'puddletag', 
            'Enter the number of files to fill the file-view with.', 10)
        if num:
            #pdb.set_trace()
            model.load(map(Tag, tags.tags[:num]))
            model.saveModification = False

    def _saveTags(self):
        files = self._status['allfiles']
        f = open('savedfiles', 'w')
        f.write(u'# -*- coding: utf-8 -*-\ntags = [%s]' % 
            u',\n'.join((unicode(z.tags) for z in files)).decode('utf8'))
        f.close()

control = ('Puddle Testing', TestWidget, RIGHTDOCK, False)
