# amarok.py

# Copyright (C) 2008-2009 concentricpuddle

# This file is part of puddletag, a semi-good music tag editor.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os

from .. import audioinfo

FILENAME = audioinfo.FILENAME
from PyQt5.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import QSettings

from mutagen.id3 import TCON

GENRES = TCON.GENRES
from .. import musiclib
from ..libraries.mysqllib import MySQLLib

name = "Amarok MySQL"
description = "Amorok Database"
author = 'concentricpuddle'

join = os.path.join
dirname = os.path.dirname


class Amarok(MySQLLib):

    def convertTrack(self, track, artist=None, album=None, convert=True):
        if artist is None:
            artist = track[-2]
        if album is None:
            album = track[-1]

        if convert:
            if track[4]:
                self.cursor.execute("SELECT DISTINCT BINARY name FROM composer WHERE id = BINARY %s", (track[4],))
                composer = self.cursor.fetchall()[0][0]
            else:
                composer = ""

            if track[5]:
                self.cursor.execute("SELECT DISTINCT BINARY name FROM genre WHERE id = BINARY %s", (track[5],))
                genre = self.cursor.fetchall()[0][0]
            else:
                genre = ""

            if track[7]:
                self.cursor.execute("SELECT DISTINCT BINARY name FROM year WHERE id = BINARY %s", (track[7],))
                year = self.cursor.fetchall()[0][0]
            else:
                year = ""
        else:
            composer = track[4]
            genre = track[5]
            year = track[7]

        filename = track[0][1:]
        temp = {'__filename': filename,
                '__folder': dirname(filename),
                '__created': audioinfo.strtime(track[2]),
                '__modified': audioinfo.strtime(track[3]),
                'album': album,
                'artist': artist,
                'composer': composer,
                'genre': genre,
                'title': track[6],
                'year': year,
                'comment': track[8],
                'track': str(track[9]),
                'discnumber': str(track[10]),
                '__bitrate': audioinfo.strbitrate(track[11] * 1000),
                '__length': audioinfo.strlength(track[12]),
                '__frequency': audioinfo.strfrequency(track[13]),
                '__size': str(track[14]),
                '___filetype': str(track[15]),
                '___sampler': str(track[16]),
                'bpm': str(track[17]),
                '___deviceid': str(track[18]),
                '__path': os.path.basename(filename),
                '__ext': os.path.splitext(filename)[1][1:],
                '__library': 'amarok'}

        return (self.applyToDict(self.applyToDict(temp, self.valuetostring),
                                 self.latinutf))

    def getArtists(self):
        self.cursor.execute("SELECT DISTINCT BINARY name FROM artist ORDER BY name")
        artists = self.cursor.fetchall()
        return [self.latinutf(artist[0]) for artist in artists]

    def getAlbums(self, artist):
        self.cursor.execute("SELECT DISTINCT BINARY id FROM artist WHERE name = BINARY %s", (self.utflatin(artist),))
        fileid = self.cursor.fetchall()[0][0]
        self.cursor.execute("SELECT DISTINCT BINARY album FROM tags WHERE artist = BINARY %s", (fileid,))
        albumids = [z[0] for z in self.cursor.fetchall()]
        albums = []
        for albumid in albumids:
            self.cursor.execute("SELECT DISTINCT BINARY name FROM album WHERE id = BINARY %s", (albumid,))
            albums.append(self.latinutf(self.cursor.fetchall()[0][0]))
        return albums

    def getTracks(self, artist, albums):
        ret = []
        if not albums:
            albums = self.getAlbums(artist)
        if self.cursor.execute("SELECT DISTINCT BINARY id FROM artist WHERE name = BINARY %s", (self.utflatin(artist),)):
            artistid = self.cursor.fetchall()[0][0]

        if not self.cursor.execute("""SELECT DISTINCT BINARY album FROM tags WHERE artist = BINARY %s""", (artistid,)):
            return []

        albumids = {}
        for albumid in [z[0] for z in self.cursor.fetchall()]:
            self.cursor.execute("""SELECT DISTINCT BINARY name FROM album WHERE id = BINARY %s""", (albumid,))
            albumids[self.cursor.fetchall()[0][0]] = albumid

        for album in albums:
            albumid = albumids[album]
            self.cursor.execute("""SELECT url, dir, createdate, modifydate,
                                composer, genre, title, year, comment,
                                track, discnumber, bitrate, length, samplerate,
                                filesize, filetype, sampler, bpm, deviceid
                                FROM tags WHERE artist = BINARY %s
                                AND album = BINARY %s""", (artistid, albumid))
            tracks = self.cursor.fetchall()
            ret.extend([musiclib.Tag(self, self.convertTrack(track, artist, album)) for track in tracks])
        return ret

    def _delTrack(self, track):
        self.cursor.execute('DELETE FROM tags WHERE url = %s', ("." + track[FILENAME],))

        for key in ('genre', 'year', 'album', 'composer', 'artist'):
            if self.cursor.execute('SELECT id FROM ' + key + ' WHERE name = BINARY %s', (track[key],)):
                keyid = self.cursor.fetchall()[0][0]
            if not self.cursor.execute('SELECT ' + key + ' FROM tags WHERE ' + key + ' = BINARY %s', (keyid,)):
                self.cursor.execute('DELETE FROM ' + key + ' WHERE id = %s', (keyid,))

    def delTracks(self, tracks):
        stringtags = audioinfo.stringtags
        app = self.applyToDict
        utflatin = self.utflatin
        for track in tracks:
            self._delTrack(app(stringtags(track, True), utflatin))

    def saveTracks(self, tracks):
        basename = os.path.basename
        freq = audioinfo.lngfrequency
        leng = audioinfo.lnglength
        stringtags = audioinfo.stringtags
        lngtime = audioinfo.lngtime
        app = self.applyToDict
        utflatin = self.utflatin

        for old, new in tracks:
            (old, new) = (app(stringtags(old, True), utflatin),
                          app(stringtags(new, True), utflatin))

            mixed = old.copy()
            mixed.update(new)
            ids = {}
            for key in ('genre', 'year', 'album', 'composer', 'artist'):
                if self.cursor.execute('SELECT id FROM ' + key + ' WHERE name = BINARY %s', (new[key],)):
                    keyid = self.cursor.fetchall()[0][0]
                else:
                    self.cursor.execute('INSERT INTO ' + key + ' VALUES (NULL, %s)', (new[key],))
                    self.cursor.execute('SELECT LAST_INSERT_ID()')
                    keyid = self.cursor.fetchall()[0][0]
                ids[key] = keyid

            url = "." + new['__filename']
            folder = "." + dirname(new['__filename'])
            self.cursor.execute("""REPLACE INTO tags VALUES (%s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s)""",
                                (url, folder, lngtime(mixed['__created']), lngtime(mixed['__modified']),
                                 ids['album'], ids['artist'], ids['composer'], ids['genre'],
                                 mixed['title'], ids['year'], mixed['comment'],
                                 mixed['track'], mixed['discnumber'],
                                 freq(mixed['__bitrate']) / 1000, leng(mixed["__length"]),
                                 freq(mixed["__frequency"]), int(mixed["__size"]),
                                 mixed['___filetype'], mixed['___sampler'], mixed['bpm'],
                                 mixed['___deviceid']))

            if old[FILENAME] != new[FILENAME]:
                self._delTrack(old)

    def search(self, term):
        self.cursor.execute('''SELECT tags.url, tags.dir, tags.createdate,
            tags.modifydate, composer.name as composer,
            genre.name as genre, tags.title, year.name as year, tags.comment,
            tags.track, tags.discnumber, tags.bitrate, tags.length,
            tags.samplerate, tags.filesize, tags.filetype, tags.sampler,
            tags.bpm, tags.deviceid,
            artist.name AS artist, album.name as album

            FROM tags, artist, album, genre, composer, year WHERE
            (tags.artist = artist.id AND tags.album = album.id
            AND tags.genre = genre.id AND tags.composer = composer.id AND
            tags.year = year.id)

            AND

            (UCASE(tags.url) REGEXP UCASE(%s) OR UCASE(artist.name) REGEXP UCASE(%s)
            OR UCASE(album.name) REGEXP UCASE(%s) OR UCASE(tags.title) REGEXP
            UCASE(%s) OR UCASE(tags.composer) REGEXP UCASE(%s) OR
            UCASE(genre.name) REGEXP UCASE(%s) OR UCASE(year.name)
            REGEXP UCASE(%s)) limit 1000''', (term,) * 7)

        return [musiclib.Tag(self, self.convertTrack(z, convert=False)) for z in self.cursor.fetchall()]

    def updateSearch(self, term, tracks):
        tags = ['artist', 'title', FILENAME, '__path', 'album', 'genre', 'comment'
            , 'composer', 'year']
        term = term.lower()
        tracks = []
        for audio in files:
            temp = audioinfo.stringtags(audio)
            for tag in tags:
                if term in temp[tag].lower():
                    tracks.append(audio)
                    break
        return tracks


class ConfigWindow(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Import Library")

        userlabel = QLabel('&Username')
        self.username = QLineEdit('amarok')
        userlabel.setBuddy(self.username)

        passlabel = QLabel('&Password')
        self.passwd = QLineEdit()
        self.passwd.setEchoMode(QLineEdit.Password)
        passlabel.setBuddy(self.passwd)

        datalabel = QLabel('&Database')
        self.database = QLineEdit('amarok')
        datalabel.setBuddy(self.database)

        portlabel = QLabel('Po&rt')
        validator = QIntValidator(self)
        self.port = QLineEdit('3306')
        portlabel.setBuddy(self.port)
        self.port.setValidator(validator)

        vbox = QVBoxLayout()
        [vbox.addWidget(z) for z in [userlabel, self.username, passlabel,
                                     self.passwd, datalabel, self.database, portlabel, self.port]]
        vbox.addStretch()
        self.setLayout(vbox)

    def getLibClass(self):
        username = str(self.username.text())
        passwd = str(self.passwd.text())
        database = str(self.database.text())
        port = int(self.port.text())

        return Amarok('tags', user=username, passwd=passwd, db=database, port=port)

    def saveSettings(self):
        username = self.username.text()
        passwd = self.passwd.text()
        database = self.database.text()
        port = self.port.text()

        settings = QSettings()
        settings.beginGroup('Library')
        settings.setValue('username', username)
        settings.setValue('passwd', passwd)
        settings.setValue('database', database)
        settings.setValue('port', port)
        settings.endGroup()

    def loadSettings(self):
        settings.beginGroup('Library')
        self.username.setText(settings.value('username'))
        self.passwd.setText(settings.value('passwd'))
        self.database.setText(settings.value('database'))
        self.port.setText(settings.value('port'))
        settings.endGroup()

        return dict(user=username, passwd=passwd, db=database, port=port)


def loadLibrary():
    settings = QSettings()
    settings.beginGroup('Library')
    username = str(settings.value('username'))
    passwd = str(settings.value('passwd'))
    database = str(settings.value('database'))
    port = int(settings.value('port'))
    return Amarok('tags', user=username, passwd=passwd, db=database, port=port)

# if __name__ == "__main__":
# db = Amarok(user = 'amarok', passwd = 'amarok', db = 'amarok')
# artist = db.getArtists()[10]
# i = db.getTracks(artist,db.getAlbums(artist))[0]
# y = i.copy()
# y[FILENAME] = './media/multi/Music/ktg.mp3'
# db.saveTracks([(i,y)])
