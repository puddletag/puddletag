#! /usr/bin/env python
#
# Search for an artist by name.
#
# Usage:
#	python findartist.py 'artist-name'
#
# $Id: findartist.py 201 2006-03-27 14:43:13Z matt $
#
from puddleobjects import unique, TableShit, OKCancel
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

CONNECTIONERROR = "Could not connect to Musicbrainz server."

class ReleaseWidget(QListWidget):
    def __init__(self, table = None, parent = None, row = 0):
        QListWidget.__init__(self, parent)
        if table is not None:
            self.table = table
        self.setCurrentRow(row)
        self.connect(self, SIGNAL("currentRowChanged(int)"), self.changeTable)
        
    def setReleases(self, releases):
        self.disconnect(self, SIGNAL("currentRowChanged(int)"), self.changeTable)
        self.tracks = {}
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
        self.connect(self, SIGNAL("currentRowChanged(int)"), self.changeTable)
    
    def changeTable(self, row):
        if row != -1:
            if row not in self.tracks:
                release = self.releases[row]
                self.emit(SIGNAL("statusChanged"), "Getting album tracks...")
                QApplication.processEvents()
                try:
                    tracks = [dict([("title", track.title), ("track", number + 1), ("album",release.title)]) 
                                    for number,track in enumerate(getalbumtracks([release])[0]["tracks"])]
                except ConnectionError:
                    self.emit(SIGNAL("statusChanged"), CONNECTIONERROR)
                    return
                except WebServiceError:
                    self.emit(SIGNAL("statusChanged"), CONNECTIONERROR + " " + details)
                    return
                self.item(row).setText(release.title + " [" + unicode(len(tracks)) + "]")
                self.tracks[row] = tracks
            else:
                tracks = self.tracks[row]
            self.emit(SIGNAL("statusChanged"), "Currently selected: " + self.item(row).text())
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
            
            
    if artistid is not None:
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
        self.table.model().unSetTestData(True)
        self.label.setText("<b>Tags were written.</b>")
        
    def closeMe(self):
        self.table.model().unSetTestData()
        self.close()
    
    def getInfo(self):
        try:            
            releasetype = RELEASETYPES[unicode(self.albumtype.currentText())]
            tags = [self.table.rowTags(z) for z in self.table.selectedRows]
            self.label.setText("Retrieving albums, please wait...")
            QApplication.processEvents()
            
            if self.combo.currentIndex() == 0:
                releases = []
                albums = unique([z['album'] for z in tags if 'album' in z])
                for z in albums:
                    album = getAlbums(album = z, releasetypes = releasetype)
                    if album:
                        releases.extend(album)
                if releases:
                    self.label.setText("The retrieved albums are listed below.")
                else:
                    self.label.setText("No albums were found by the selected artists.")
                QApplication.processEvents()
                self.listbox.setReleases(releases)
                return
            
            elif self.combo.currentIndex() == 1:                
                artists = getArtist(tags)
                releases = []
                text = "The following artist's album's were retrieved: "
                QApplication.processEvents()
                for z in artists:
                    artistname = z[0]
                    artistid = z[1][1]
                    albums = getAlbums(artistid, releasetypes = releasetype)
                    if albums:
                        releases.extend(albums)
                        text = text + artistname + ", "
                self.label.setText(text[:-2])
                if releases:
                    self.listbox.setReleases(releases)
                else:
                    self.label.setText("No albums were found by the selected artists.")
                return
            
            elif self.combo.currentIndex() == 2:
                artists = [getArtist(tags)[0]]
                album = unique([z['album'] for z in tags if 'album' in z])[0]
                for z in artists:
                    artistid = z[1][1]
                    albumtracks = getAlbums(artistid, album,releasetypes = releasetype)
                    QApplication.processEvents()
                    if albumtracks:
                        if len(albumtracks == 1):
                            self.listbox.setReleases(albumtracks)
                            self.label.setText("Found album " + album + ". Click on Write Tags to save the tags.")
                            self.listbox.setCurrentIndex(0)
                        else:
                            self.label.setText("I couldn't find an exact match to the album you specified.")
                            self.listbox.setReleases(albumtracks)                            
                return
        
        except (ConnectionError, WebServiceError):
            self.label.setText(CONNECTIONERROR)
        except WebServiceError, details:
            self.label.setText(CONNECTIONERROR + " " + details)
        return
