# prokyon.py

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
import pdb

from .. import audioinfo

FILENAME = audioinfo.FILENAME
from PyQt5.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import QSettings
from mutagen.id3 import TCON

GENRES = TCON.GENRES
from .. import musiclib
from ..libraries.mysqllib import MySQLLib

name = "Prokyon"
description = "Prokyon Database"
author = 'concentricpuddle'

PROKYONTAGS = {'__path': 'filename',
               '__folder': 'path',
               '__bitrate': 'bitrate',
               '__frequency': 'samplerate',
               '__length': 'length',
               'title': 'title',
               'track': 'title',
               'year': 'title',
               'genre': 'genre',
               'comment': 'comment',
               '__size': 'size',
               '__modified': 'modified',
               'artist': 'artist',
               'album': 'album',
               "layer": 'layer',
               '___mimetype': 'mimetype',
               '___version': 'version',
               '___mode': 'mode',
               '___lyricsid': 'lyrics_id',
               '___synclyricsid': 'synced_lyrics_id',
               '___notes': 'notes',
               '___rating': 'rating',
               '___medium': 'medium'}


def prokyontag(tag):
    ret = PROKYONTAGS[tag]
    if isinstance(ret, str):
        return ret
    else:
        return ret(tag)


SUPPORTEDTAGS = ['artist', 'album', 'title', 'year', 'track']


class Prokyon(MySQLLib):
    def getArtists(self):
        return self.distinctValues('artist')

    def getAlbums(self, artist):
        return self.children('artist', artist, 'album')

    def convertTrack(self, track, artist=None, album=None):
        join = os.path.join
        if artist is None:
            # print len(track), track
            try:
                artist = track[21]
            except:
                print(track.tags)
                raise

        if album is None:
            album = track[22]
        try:
            genre = GENRES[track[8]]
        except (IndexError, TypeError):
            genre = ''

        temp = {'__filename': join(track[0], track[1]),
                '__path': track[1],
                '__ext': os.path.splitext(track[1])[1][1:],  # Don't need(or want) the extra dot
                '__bitrate': audioinfo.strbitrate(track[2] * 1000),
                '__frequency': audioinfo.strfrequency(track[3]),
                '__length': audioinfo.strlength(track[4]),
                '__folder': track[0],
                'title': track[5],
                'track': track[6],
                'year': track[7],
                'genre': genre,
                'comment': track[9],
                '__size': track[10],
                '__modified': track[11],
                'artist': artist,
                'album': album,
                '__library': 'prokyon',
                "___layer": track[12],
                '___mimetype': track[13],
                '___version': track[14],
                '___mode': track[15],
                '___lyricsid': track[16],
                '___synclyricsid': track[17],
                '___notes': track[18],
                '___rating': track[19],
                '___medium': track[20]}

        return self.applyToDict(self.applyToDict(temp, self.valuetostring), self.latinutf)

    def distinctValues(self, tag):
        if tag not in SUPPORTEDTAGS:
            return
        s = 'SELECT DISTINCT BINARY ' + PROKYONTAGS[tag] + ' FROM tracks ' + \
            'ORDER BY ' + PROKYONTAGS[tag]
        self.cursor.execute(s)
        return [str(artist[0], 'utf8') for artist in self.cursor.fetchall()]

    def children(self, parent, parentvalue, child):
        self.cursor.execute("SELECT DISTINCT BINARY " + PROKYONTAGS[child] + \
                            " FROM tracks WHERE " + PROKYONTAGS[parent] + " = BINARY %s",
                            (parentvalue))
        return [self.latinutf(album[0]) for album in self.cursor.fetchall()]

    def tracksByTag(self, parent, parentvalue, child=None, childval=None):
        if parent not in SUPPORTEDTAGS:
            return
        if child is None:
            s = """SELECT path, filename, bitrate,
                    samplerate, length, title, tracknumber, year, genre,
                    comment, size, lastModified, layer, mimetype,
                    version, mode, lyrics_id, synced_lyrics_id, notes,rating,
                    medium, artist, album FROM tracks WHERE """ + \
                PROKYONTAGS[parent] + " = BINARY %s"
            self.cursor.execute(s, (parentvalue,))
            tracks = self.cursor.fetchall()
        else:
            if childval is None:
                children = self.children(parent, parentvalue, child)
                tracks = [self.tracksByTag(parent, parentvalue, child, cval)
                          for cval in children]
                return tracks
            else:
                s = """SELECT path, filename, bitrate,
                    samplerate, length, title, tracknumber, year, genre,
                    comment, size, lastModified, layer, mimetype,
                    version, mode, lyrics_id, synced_lyrics_id, notes,rating,
                    medium, artist, album FROM tracks WHERE """ + \
                    PROKYONTAGS[parent] + " = BINARY %s AND " + \
                    PROKYONTAGS[child] + " = BINARY %s"
                self.cursor.execute(s, (parentvalue, childval))
                tracks = self.cursor.fetchall()
        return [musiclib.Tag(self, self.convertTrack(track)) for track in tracks]

    def getTracks(self, artist, albums=None):
        ret = []
        artist = self.utflatin(artist)
        if albums is None:
            albums = self.getAlbums(artist)
        for album in albums:
            try:
                album = self.utflatin(album)
            except Exception as e:
                print('artist:', artist, 'album', album)
                raise e
            if not album:
                self.cursor.execute("""SELECT path, filename, bitrate,
                samplerate, length, title, tracknumber, year, genre,
                comment, size, lastModified, layer, mimetype,
                version, mode, lyrics_id, synced_lyrics_id, notes,rating,
                medium FROM tracks WHERE artist = BINARY %s
                AND (album = '' or album is NULL)""", (artist,))
            else:
                self.cursor.execute("""SELECT path, filename, bitrate,
                samplerate, length, title, tracknumber, year, genre,
                comment, size, lastModified, layer, mimetype,
                version, mode, lyrics_id, synced_lyrics_id, notes,rating,
                medium FROM tracks WHERE artist = BINARY %s
                AND album = BINARY %s""", (artist, album))

            tracks = self.cursor.fetchall()
            ret.extend([musiclib.Tag(self, self.convertTrack(track, artist, album)) for track in tracks])
        return ret

    def delTracks(self, tracks):
        dirname = os.path.dirname
        basename = os.path.basename

        for track in tracks:
            filename = basename(track[FILENAME])
            path = dirname(track[FILENAME])

            if self.cursor.execute('''SELECT id FROM tracks WHERE path = BINARY
                            %s AND filename = BINARY %s''', (path, filename)):
                fileid = self.cursor.fetchall()[0][0]
                self.cursor.execute('DELETE FROM tracks WHERE id = %s', (fileid,))

            artist = track['artist'][0]
            if self.cursor.execute('''SELECT id, total FROM artists WHERE
                name = BINARY %s''', (artist,)):
                (fileid, tks) = self.cursor.fetchall()[0]
                if tks <= 1:
                    self.cursor.execute('DELETE FROM artists WHERE id = %s', (fileid,))
                else:
                    self.cursor.execute('''UPDATE artists SET total = total - 1,
                        local = local - 1 WHERE id = %s''', (fileid,))

            album = track['album'][0]
            if self.cursor.execute('''SELECT id, tracks_available FROM albums
                WHERE artist = BINARY %s AND name = BINARY %s''', (artist, album)):
                (fileid, tks) = self.cursor.fetchall()[0]
                if tks > 1:
                    self.cursor.execute('UPDATE albums SET tracks_available = tracks_available - 1 WHERE id = %s', (fileid,))
                else:
                    self.cursor.execute('DELETE FROM albums WHERE id = %s', (fileid,))

    def saveTracks(self, tracks):
        dirname = os.path.dirname
        basename = os.path.basename
        freq = audioinfo.lngfrequency
        leng = audioinfo.lnglength
        stringtags = audioinfo.stringtags
        utflatin = self.utflatin
        appDict = self.applyToDict

        def genretoint(genre):
            try:
                return GENRES.index(genre)
            except ValueError:
                return 255

        for old, new in tracks:
            pdb.set_trace()
            (old, new) = (stringtags(old, True), stringtags(new, True))
            mixed = old.copy()
            mixed.update(new)
            mixed = appDict(appDict(mixed, self.utflatin), self.strToNone)
            for z in ['artist', 'album', 'title']:
                try:
                    if mixed[z] is None:
                        mixed[z] = ""
                except KeyError:
                    mixed[z] = ""

            oldfilename = utflatin(basename(old['__filename']))
            oldpath = utflatin(dirname(old['__filename']))
            old = appDict(old, utflatin)

            newfilename = basename(mixed['__filename'])
            newpath = dirname(mixed['__filename'])
            # Check if the new file exists in the table, delete the row if it does
            # since filenames have to be unique.

            if self.cursor.execute('SELECT id FROM tracks WHERE path = BINARY %s AND filename = BINARY %s', (newpath, newfilename)):
                fileid = self.cursor.fetchall()[0][0]
                self.cursor.execute('DELETE FROM tracks WHERE id = %s', (fileid,))

            # Update the old file if it exists. Create new one otherwise.
            if self.cursor.execute('SELECT id FROM tracks WHERE path = BINARY %s AND filename = BINARY %s', (oldpath, oldfilename)):
                fileid = self.cursor.fetchall()[0][0]
            else:
                self.cursor.execute('SELECT MAX(id) FROM tracks')
                fileid = self.cursor.fetchall()[0][0] + 1

            self.cursor.execute("""REPLACE INTO tracks VALUES
                            (%s, %s, %s, %s, %s,
                            0, %s, %s, %s ,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s)""",
                                (fileid, newpath, newfilename, mixed['___medium'], mixed['__modified'],
                                 mixed['___mimetype'], mixed['___version'], mixed['___layer'],
                                 mixed['___mode'], freq(mixed['__bitrate']) / 1000, freq(mixed["__frequency"]),
                                 leng(mixed["__length"]), int(mixed["__size"]),
                                 mixed["artist"], mixed["title"], mixed['___lyricsid'], mixed['___synclyricsid'], mixed['album'], mixed['track'],
                                 mixed['year'], genretoint(mixed['genre']), mixed["comment"],
                                 mixed['___notes'], mixed['___rating']))

            # Update artists table
            artist = mixed['artist']

            if self.cursor.execute('SELECT id FROM artists WHERE name = BINARY %s', (artist,)):
                fileid = self.cursor.fetchall()[0][0]
                self.cursor.execute('UPDATE artists SET total = total + 1, local = local + 1 WHERE id = %s', (fileid,))
            else:
                self.cursor.execute('SELECT MAX(id) FROM artists')
                fileid = self.cursor.fetchall()[0][0] + 1
                self.cursor.execute('''REPLACE INTO artists VALUES (%s, %s, 1, 1, 0, NULL, NULL, NULL)''', (fileid, artist))

            if self.cursor.execute('SELECT id, total FROM artists WHERE name = BINARY %s',
                                   (old['artist'],)):
                (oldid, oldtks) = self.cursor.fetchall()[0]
                if oldtks <= 1:
                    self.cursor.execute('DELETE FROM artists WHERE id = %s', (oldid,))
                else:
                    self.cursor.execute('UPDATE artists SET total = total - 1, local = local - 1 WHERE id = %s', (oldid,))

            # Update albums table.
            album = mixed['album']
            artist = mixed['artist']

            if self.cursor.execute('SELECT id FROM albums WHERE artist = BINARY %s AND name = BINARY %s', (artist, album)):
                fileid = self.cursor.fetchall()[0][0]
                self.cursor.execute('UPDATE albums SET tracks_available = tracks_available + 1 WHERE id = %s', (fileid,))
            else:
                self.cursor.execute('SELECT MAX(id) FROM albums')
                fileid = self.cursor.fetchall()[0][0] + 1
                self.cursor.execute('''REPLACE INTO albums
                                        VALUES (%s, %s, %s, 1, NULL, NULL, NULL, NULL)''',
                                    (fileid, album, artist))

            self.cursor.execute('SELECT id, tracks_available FROM albums WHERE artist = BINARY %s AND name = BINARY %s', (old['artist'], old['album']))
            try:
                (oldid, oldtks) = self.cursor.fetchall()[0]
                if oldtks > 1:
                    self.cursor.execute('UPDATE albums SET tracks_available = tracks_available - 1 WHERE id = %s', (oldid,))
                else:
                    self.cursor.execute('DELETE FROM albums WHERE id = %s', (oldid,))
            except IndexError:
                "No need to do any removing since old['album'] does not exist in the database."

    def search(self, term):
        self.cursor.execute("""SELECT path, filename, bitrate,
                samplerate, length, title, tracknumber, year, genre,
                comment, size, lastModified, layer, mimetype,
                version, mode, lyrics_id, notes,rating,
                medium, artist, album FROM tracks WHERE
                UCASE(artist) REGEXP(%s) or UCASE(filename) REGEXP(%s) or
                UCASE(title) REGEXP(%s) or UCASE(path) REGEXP(%s) or
                UCASE(album) REGEXP(%s) or UCASE(genre) REGEXP(%s) or
                UCASE(comment) REGEXP(%s) or UCASE(notes) REGEXP(%s) or
                UCASE(year) REGEXP(%s)
                """, (term,) * 9)
        return [musiclib.Tag(self, self.convertTrack(track)) for track in self.cursor.fetchall()]

    def updateSearch(self, term, files):
        tags = ['artist', 'title', FILENAME, '__path', 'album', 'genre', 'comment'
            , '___notes', 'year']
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
        self.username = QLineEdit('prokyon')
        userlabel.setBuddy(self.username)

        passlabel = QLabel('&Password')
        self.passwd = QLineEdit()
        self.passwd.setEchoMode(QLineEdit.Password)
        passlabel.setBuddy(self.passwd)

        datalabel = QLabel('&Database')
        self.database = QLineEdit('prokyon')
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

        return Prokyon('tracks', user=username, passwd=passwd, db=database, port=port)

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
    return Prokyon(user=username, passwd=passwd, db=database, port=port)


if __name__ == "__main__":
    p = Prokyon('tracks', user="prokyon", passwd='prokyon', db='prokyon')
    print([p.getTracks(z, p.getAlbums(z)) for z in p.getArtists()[:10]])
