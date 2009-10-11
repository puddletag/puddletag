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
from puddleobjects import unique, OKCancel
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys, pdb
from musicbrainz2.webservice import Query, ArtistFilter, WebServiceError, ConnectionError
import musicbrainz2.webservice as ws
import musicbrainz2.model as brainzmodel

class MyThread(QThread):
    def __init__(self, command, parent = None):
        QThread.__init__(self, parent)
        self.command = command
    def run(self):
        self.retval = self.command()

RELEASETYPES = {"Official Albums": [brainzmodel.Release.TYPE_OFFICIAL],
"Promotional Album": [brainzmodel.Release.TYPE_PROMOTION],
"Bootlegs": [brainzmodel.Release.TYPE_BOOTLEG]
}

CONNECTIONERROR = "Could not connect to Musicbrainz server.(Check your net connection)"

class ReleaseWidget(QListWidget):
    def __init__(self, table = None, parent = None, row = 0):
        QListWidget.__init__(self, parent)
        if table is not None:
            self.table = table
        self.currentrow = row
        self.tracks = {}
        self.connect(self, SIGNAL('itemClicked(QListWidgetItem *)'), self.changeTable)

    def setReleases(self, releases):
        self.disconnect(self, SIGNAL('itemClicked(QListWidgetItem *)'), self.changeTable)
        self.clear()
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
            self.addItems([z.artist.name + ": " + z.title for z in releases])
        except AttributeError:
            self.addItems(sorted([z.title + unicode(year) for z, year in zip(releases, years)]))
        self.releases = releases
        if releases:
            self.setCurrentRow(self.currentrow)
            if len(releases) == 1:
               self.changeTable(self.item(0))
        self.connect(self, SIGNAL('itemClicked(QListWidgetItem *)'), self.changeTable)

    def changeTable(self, item):
        row = self.row(item)
        self.dirtyrow = row
        if row > -1:
            if row not in self.tracks:
                release = self.releases[row]
                self.emit(SIGNAL("statusChanged"), "Getting album tracks...")
                QApplication.processEvents()
                def func():
                    try:
                        tracks = [dict([("title", track.title), ("track", unicode(number + 1)), ("album",release.title)])
                                        for number,track in enumerate(getalbumtracks([release])[0]["tracks"])]
                    except ConnectionError:
                        return {'tracks':[], 'text': CONNECTIONERROR}
                    except WebServiceError:
                        return {'tracks':[], 'text': CONNECTIONERROR + " " + details}
                    return {'tracks':tracks, 'text':"", 'releasetitle': release.title}
                self.t = MyThread(func)
                self.connect(self.t, SIGNAL("finished()"), self.showAlbum)
                self.t.start()
            else:
                self.showAlbum()

    def showAlbum(self):
        text = self.t.retval['text']
        releasetitle = self.t.retval['releasetitle']

        if text:
            self.emit(SIGNAL("statusChanged"), self.retval.t['text'])
            return

        if self.dirtyrow not in self.tracks:
            tracks = self.t.retval['tracks']
            self.item(self.dirtyrow).setText(releasetitle + " [" + unicode(len(tracks)) + "]")
            self.tracks[self.dirtyrow] = tracks
        else:
            tracks = self.tracks[self.dirtyrow]
        self.emit(SIGNAL("statusChanged"), "Currently selected: " + self.item(self.dirtyrow).text())
        self.table.model().setTestData(self.table.selectedRows, tracks[:len(self.table.selectedRows)])

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
                    text = "No albums were found with the matching criteria."
                return {'releases': releases, 'text':text}

            self.t = MyThread(func)
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
            self.t = MyThread(func)
            self.connect(self.t, SIGNAL("finished()"), self.showAlbums)
            self.t.start()


        elif self.combo.currentIndex() == 2:
            def func():
                try:
                    artists = [getArtist(tags)[0]]
                except (WebServiceError, ConnectionError):
                    return {'releases': [], 'text': CONNECTIONERROR}
                album = unique([z['album'] for z in tags if 'album' in z])[0]
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
            self.t = MyThread(func)
            self.connect(self.t, SIGNAL("finished()"), self.showAlbums)
            self.t.start()

    def showAlbums(self):
        self.listbox.setReleases(self.t.retval['releases'])
        self.label.setText(self.t.retval['text'])
        self.getinfo.setEnabled(True)