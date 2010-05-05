#! /usr/bin/env python
# -*- coding: utf-8 -*-
#webdb.py

#Copyright (C) 2008-2009 concentricpuddle

#This file is part of puddletag, a semi-good music tag editor.

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
import sys, pdb
from puddlestuff.util import split_by_tag
from puddlestuff.puddleobjects import PuddleConfig, OKCancel, winsettings
locales = ["us", "uk", "de", "jp"]
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import amazon, puddlestuff.tagsources as tagsources

class Config(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        cparser = PuddleConfig()
        winsettings('amazontagsource', self)
        license = cparser.get('amazontagsource', 'license', "1HQ4DDKC5D23SWM4V2R2")
        locale = cparser.get('amazontagsource', 'locale', 0)
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        self._license = QLineEdit("1HQ4DDKC5D23SWM4V2R2")
        label = QLabel('&License: ')
        label.setToolTip('Go to http://www.amazon.com/webservices to get one.')
        label.setBuddy(self._license)

        hbox = QHBoxLayout()
        hbox.addWidget(label)
        hbox.addWidget(self._license)
        vbox.addLayout(hbox)

        self._locale = QComboBox()
        self._locale.addItems(locales)
        self._locale.setCurrentIndex(locale)
        label = QLabel('&Locale: ')
        label.setBuddy(self._locale)

        hbox = QHBoxLayout()
        hbox.addWidget(label)
        hbox.addWidget(self._locale)
        vbox.addLayout(hbox)

        okcancel = OKCancel()
        vbox.addLayout(okcancel)
        self.connect(okcancel, SIGNAL('ok'), self._configured)
        self.connect(okcancel, SIGNAL('cancel'), self.close)

    def _configured(self):
        locale = locales[self._locale.currentIndex()]
        license = unicode(self._license.text())
        cparser = PuddleConfig()
        cparser.set('amazontagsource', 'license', license)
        cparser.set('amazontagsource', 'locale', self._locale.currentIndex())
        self.emit(SIGNAL('tagsourceprefs'), locale, license)
        self.close()

class Amazon(object):
    def search(self, audios=None, params=None):
        self._artistids = {}
        self._releases = {}
        ret = defaultdict(lambda:{})
        self._cache = defaultdict(lambda:{})
        tracks = True
        if not params:
            tracks = None
            params = split_by_tag(audios)
        exactmatches = {}
        for artist, albums in params.items():
            if artist:
                for album in albums:
                    try:
                        url, linkurl = amazon.search(artist, album)
                        self._cache[artist][album] = linkurl
                        if tracks:
                            cover = self._retrievecover(url, artist, album)
                            self._cache[artist][album] = cover
                            for track in albums[album]:
                                exactmatches[track] = {'__image': cover,
                                    'artist': artist,
                                    'album': album,
                                    'track': track.sget('track')}
                    except amazon.AmazonError, e:
                        raise RetrievalError(unicode(e))
        return ret, exactmatches

    def retrieve(self, artist, album):
        if isinstance(self._cached[artist][album], basestring):
            cover = self._retrievecover(url, artist, album)
            self._cache[artist][album] = cover
            return {'__image': cover,
                    'artist': artist,
                    'album': album}
        return get_tracks(r_id)

    def _retrievecover(self, url, artist, album):
        i = urllib.urlopen(url)
        filename = os.path.join(tagsources.COVERDIR, u'%s - %s.jpg' % (
                                artist, album))
        data = i.read()
        f = open(filename, 'wb')
        f.write(data)
        f.close()
        return {'data': data, 'filename': filename}

    def applyPrefs(self, locale, license):
        amazon.setLicense(license)
        amazon.setLocale(locale)

info = [Amazon, Config]
name = 'Amazon'