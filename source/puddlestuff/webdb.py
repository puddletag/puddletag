#! /usr/bin/env python
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
from puddleobjects import unique, OKCancel, PuddleThread
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys, pdb
from musicbrainz2.webservice import Query, ArtistFilter, WebServiceError, ConnectionError
import musicbrainz2.webservice as ws
import musicbrainz2.model as brainzmodel

RELEASETYPES = {"Official Albums": [brainzmodel.Release.TYPE_OFFICIAL],
"Promotional Album": [brainzmodel.Release.TYPE_PROMOTION],
"Bootlegs": [brainzmodel.Release.TYPE_BOOTLEG]
}

CONNECTIONERROR = "Could not connect to Musicbrainz server.(Check your net connection)"

class ReleaseWidget(QTreeWidget):
    def __init__(self, table = None, parent = None):
        QTreeWidget.__init__(self, parent)

        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        if table is not None:
            self.table = table
        self.tracks = {}
        self._dirtyrow = 0
        self.connect(self, SIGNAL('itemSelectionChanged()'), self._selChanged)
        self.connect(self, SIGNAL('itemCollapsed (QTreeWidgetItem *)'), self.setClosedIcon)
        self.connect(self, SIGNAL('itemExpanded (QTreeWidgetItem *)'), self.setOpenIcon)


    def setClosedIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirClosedIcon))

    def setOpenIcon(self, item):
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirOpenIcon))
        row = self.indexOfTopLevelItem(item)
        if row not in self.tracks:
            self.gettracks([row])

    def _selChanged(self):
        rowindex = self.indexOfTopLevelItem
        toplevels = [z for z in self.selectedItems() if not z.parent()]
        if toplevels:
            toprows = [rowindex(z) for z in toplevels]
            t = [z for z in toprows if z not in self.tracks]
            if t:
                self.gettracks(t)
                return
        self._selectedTracks()
        #self.emit(SIGNAL("statusChanged"), "Selection changed.")

    def _selectedTracks(self):
        rowindex = self.indexOfTopLevelItem
        selected = self.selectedItems()
        tracks = []
        toplevels = [z for z in selected if not z.parent()]
        if toplevels:
            children = [z for z in selected if z.parent() and z.parent() not in toplevels]
            toprows = [rowindex(z) for z in toplevels]
            [tracks.extend(self.tracks[z]) for z in toprows]
        else:
            children = selected

        for child in children:
            parent = child.parent()
            tracks.append(self.tracks[rowindex(parent)][parent.indexOfChild(child)])

        self.table.model().setTestData(self.table.selectedRows, tracks[:len(self.table.selectedRows)])

    def gettracks(self, rows):
        try:
            while self.t.isRunning():
                pass
        except AttributeError:
            pass

        self.emit(SIGNAL("statusChanged"), "Retrieving album tracks...")
        QApplication.processEvents()
        def func():
            total = {}
            for row in rows:
                release = self.releases[row]
                try:
                    total[row] = [dict([("title", track.title), ("track", unicode(number + 1)), ("album",release.title)])
                                    for number,track in enumerate(getalbumtracks([release])[0]["tracks"])]
                except ConnectionError:
                    return {'tracks':{}, 'text': CONNECTIONERROR}
                except WebServiceError:
                    return {'tracks':{}, 'text': CONNECTIONERROR + " " + details}
            return {'tracks':total, 'text':"", 'releasetitle': release.title}
        self.t = PuddleThread(func)
        self.connect(self.t, SIGNAL("threadfinished"), self.updateStatus)
        self.t.start()


    def setReleases(self, releases):
        self.clear()
        self.tracks = {}
        self._dirtyrow = 0
        rels = sorted([[z.title, z] for z in releases])
        releases = [z[1] for z in rels]
        events = [z.getReleaseEventsAsDict() for z in releases]
        years = []
        for i,event in enumerate(events):
            if event:
                years.append(" (" + unicode(event.values()[0]) +") ")
            else:
                years.append("")
        try:
            text = [z.artist.name + " - "+ z.title for z in releases]
        except AttributeError:
            text = sorted([z.title + unicode(year) for z, year in zip(releases, years)])

        for t in text:
            item = QTreeWidgetItem([t])
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            item.setIcon(0,self.style().standardIcon(QStyle.SP_DirOpenIcon))
            [self.addTopLevelItem(item) for t in text]
        self.releases = releases

    def updateStatus(self, val):
        if not val:
            self.emit(SIGNAL("statusChanged"), 'An unexpected error occurred.')
            return
        text = val['text']
        if text:
            self.emit(SIGNAL("statusChanged"), text)
            return
        tracks = val['tracks']
        self.tracks.update(tracks)
        for row in tracks:
            item = self.topLevelItem(row)
            item.takeChildren()
            item.setText(0, item.text(0) + '[%d]' % len(tracks[row]))
            [item.addChild(QTreeWidgetItem([z['title']])) for z in tracks[row]]
        self.emit(SIGNAL("statusChanged"), "Track retrieval successful.")
        self._selectedTracks()

def getArtist(tags):
    """If tags is a dictionary, getArtist will loop through it
    find the musicbrainz2 artist ids of all the artists and return them in a list

    Same goes for if tags is string(i.e a list is returned)"""
    q = Query()
    if (type(tags) is unicode) or (type(tags) is str):
        artists = [tags]
    else:
        artists = unique([z['artist'] for z in tags if 'artist' in z])
    if not artists:
        return

    artistids = []
    for artist in artists:
        results = q.getArtists(ArtistFilter(artist, limit = 1))
        if results:
            artistids.append([artist,[results[0].artist.name, results[0].artist.id]])
    return artistids

def getalbumtracks(releases):
        q = Query()
        tracks = []
        inc = ws.ReleaseIncludes(discs=True, tracks=True, artist = True, releaseEvents = True)
        for release in releases:
                release = q.getReleaseById(release.id, inc)
                releasetracks = release.getTracks()
                tracks.append(releasetracks)
        return unique([dict([("album", release.title), ("tracks", tracklist)]) for release, tracklist in zip(releases, tracks)])

def getAlbums(artistid = None, album = None, releasetypes = None):
    q = Query()
    if releasetypes is None:
        releasetypes = [brainzmodel.Release.TYPE_OFFICIAL]

    if artistid is None and album is not None:
        release = ws.ReleaseFilter(title = album, releaseTypes = releasetypes, limit = 10)
        releases = [z.getRelease() for z in q.getReleases(release)]
        if releases:
            return releases


    elif artistid is not None:
        artist = q.getArtistById(artistid,
                    ws.ArtistIncludes(releases=releasetypes))
        releases = artist.getReleases()
        if releases:
            if album is not None:
                album = album.lower()
                myrel = [release for release in releases if release.title.lower().find(album) != -1]
                return myrel
            else:
                return releases

class MainWin(QDialog):
    def __init__(self, table, parent = None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("puddletag Musicbrainz")
        self.table = table
        self.combo = QComboBox()
        self.combo.addItems(["Album only", "Artist only", "Album and Artist"])
        self.combo.setCurrentIndex(0)

        self.albumtype = QComboBox()
        self.albumtype.addItems([z for z in RELEASETYPES])
        self.albumtype.setCurrentIndex(self.albumtype.findText("Official Albums"))

        self.getinfo = QPushButton("Get Info")
        self.connect(self.getinfo , SIGNAL("clicked()"), self.getInfo)

        self.okcancel = OKCancel()
        self.okcancel.ok.setText("&Write tags")
        self.okcancel.cancel.setText("&Close")
        clearcache = QPushButton("Clea&r tags")
        self.okcancel.insertWidget(2,clearcache)

        self.connect(self.okcancel, SIGNAL("ok"), self.writeVals)
        self.connect(self.okcancel, SIGNAL("cancel"), self.closeMe)
        self.connect(self,SIGNAL('rejected()'), self.closeMe)
        self.connect(clearcache, SIGNAL("clicked()"), self.table.model().unSetTestData)

        self.label = QLabel("Select files and click on Get Info to retrieve metadata.")

        self.listbox = ReleaseWidget(table)
        self.connect(self.listbox, SIGNAL('statusChanged'), self.label.setText)

        hbox = QHBoxLayout()

        hbox.addWidget(self.combo,1)
        hbox.addWidget(self.albumtype,1)
        hbox.addWidget(self.getinfo)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.label)
        vbox.addWidget(self.listbox, 1)
        vbox.addLayout(self.okcancel)


        self.setLayout(vbox)
        self.show()

    def writeVals(self):
        self.table.model().unSetTestData(True)(self)
        self.label.setText("<b>Tags were written.</b>")

    def closeMe(self):
        self.table.model().unSetTestData()
        self.close()

    def getInfo(self):
        self.getinfo.setEnabled(False)
        releasetype = RELEASETYPES[unicode(self.albumtype.currentText())]
        tags = [self.table.rowTags(z).stringtags() for z in self.table.selectedRows]
        self.label.setText("Retrieving albums, please wait...")
        QApplication.processEvents()

        if self.combo.currentIndex() == 0:
            releases = []
            albums = unique([z['album'] for z in tags if 'album' in z])
            def func():
                text = ""
                for z in albums:
                    try:
                        album = getAlbums(album = z, releasetypes = releasetype)
                    except (WebServiceError, ConnectionError):
                        text = CONNECTIONERROR
                        break
                    if album:
                        releases.extend(album)
                if releases:
                    text = text + " " + "The retrieved albums are listed below."
                else:
                    text = "No matching albums were found."
                return {'releases': releases, 'text':text}

            self.t = PuddleThread(func)
            self.connect(self.t, SIGNAL("finished()"), self.showAlbums)
            self.t.start()


        elif self.combo.currentIndex() == 1:
            def func():
                try:
                    artists = getArtist(tags)
                except (WebServiceError, ConnectionError):
                    return {'releases': [], 'text': CONNECTIONERROR}
                releases = []
                text = "The following artist's album's were retrieved: "
                for z in artists:
                    artistname = z[0]
                    artistid = z[1][1]
                    try:
                        albums = getAlbums(artistid, releasetypes = releasetype)
                    except (ConnectionError, WebServiceError):
                        if releases:
                            text = CONNECTIONERROR + " " + text
                        else:
                            text = CONNECTIONERROR
                        break
                    if albums:
                        releases.extend(albums)
                        text = text + artistname + ", "
                if releases:
                    return {'releases': releases, 'text':text[:-2]}
                else:
                    return {'releases': releases, 'text':"No albums were found matching the selected artists"}
            self.t = PuddleThread(func)
            self.connect(self.t, SIGNAL("finished()"), self.showAlbums)
            self.t.start()


        elif self.combo.currentIndex() == 2:
            def func():
                album = unique([z['album'] for z in tags if 'album' in z])
                if not album:
                    return {'releases':[], 'text': "There's no album in the selected tags. <br />Please choose another method te retrieval method."}

                album = album[0]
                try:
                    artists = [getArtist(tags)[0]]
                except (WebServiceError, ConnectionError):
                    return {'releases': [], 'text': CONNECTIONERROR}

                for z in artists:
                    artistid = z[1][1]
                    try:
                        releases = getAlbums(artistid, album,releasetypes = releasetype)
                    except (WebServiceError, ConnectionError):
                        return {'releases': releases, 'text':CONNECTIONERROR}
                    if releases:
                        if len(releases) == 1:
                            text = "Found album " + album + ". Click on Write Tags to save the tags."
                        else:
                            text = "I couldn't find an exact match to the album you specified."
                    else:
                        releases = []
                        text = "I couldn't find any albums by the selected artist."
                return {'releases': releases, 'text':text}
            self.t = PuddleThread(func)
            self.connect(self.t, SIGNAL("finished()"), self.showAlbums)
            self.t.start()

    def showAlbums(self):
        self.listbox.setReleases(self.t.retval['releases'])
        self.label.setText(self.t.retval['text'])
        self.getinfo.setEnabled(True)