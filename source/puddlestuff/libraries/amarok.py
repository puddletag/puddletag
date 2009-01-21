import MySQLdb as mysql
import sys, os, pdb
sys.path.insert(1, '..')
import audioinfo, pdb
from operator import itemgetter
FILENAME = audioinfo.FILENAME
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from mutagen.id3 import TCON
GENRES = TCON.GENRES
import musiclib

name = "Amarok"
description = "Amorok Database"
author = 'concentricpuddle'

class Amarok:
    def __init__(self, **keywords):
        keywords['use_unicode'] = True
        keywords['charset'] = 'utf8'
        self.db = mysql.connect(**keywords)
        self.cursor = self.db.cursor()

    def getArtists(self):
        self.cursor.execute(u"SELECT DISTINCT BINARY name FROM artist ORDER BY name")
        artists = self.cursor.fetchall()
        return [z[0] for z in artists]

    def getAlbums(self, artist):
        self.cursor.execute(u"SELECT DISTINCT BINARY id FROM artist WHERE name = BINARY %s", (artist,))
        fileid = self.cursor.fetchall()[0][0]
        self.cursor.execute(u"SELECT DISTINCT BINARY album FROM tags WHERE artist = BINARY %s", (fileid,))
        albumid = [z[0] for z in self.cursor.fetchall()]
        albums = []
        for z in albumid:
            self.cursor.execute(u"SELECT DISTINCT BINARY name FROM album WHERE id = BINARY %s", (z,))
            albums.append(self.cursor.fetchall()[0][0])
        return albums

    def getTracks(self, artist, albums):
        join = os.path.join
        dirname = os.path.dirname
        ret = []
        if self.cursor.execute(u"SELECT DISTINCT BINARY id FROM artist WHERE name = BINARY %s", (artist,)):
            artistid = fileid = self.cursor.fetchall()[0][0]

        if not self.cursor.execute(u"""SELECT DISTINCT BINARY album FROM tags WHERE artist = BINARY %s""", (artistid,)):
            return []

        albumids = {}
        for albumid in [z[0] for z in self.cursor.fetchall()]:
            self.cursor.execute(u"""SELECT DISTINCT BINARY name FROM album WHERE id = BINARY %s""", (albumid,))
            albumids[self.cursor.fetchall()[0][0]] = albumid

        for album in albums:
            albumid = albumids[album]
            self.cursor.execute(u"""SELECT url, dir, createdate, modifydate,
                                composer, genre, title, year, comment,
                                track, discnumber, bitrate, length, samplerate,
                                filesize, filetype, sampler, bpm, deviceid
                                FROM tags WHERE artist = BINARY %s
                                AND album = BINARY %s""", (artistid, albumid))
            tracks = self.cursor.fetchall()
            for track in tracks:
                if track[4]:
                    self.cursor.execute(u"SELECT DISTINCT BINARY name FROM composer WHERE id = BINARY %s", (track[4],))
                    composer = self.cursor.fetchall()[0][0]
                else:
                    composer = u""

                if track[5]:
                    self.cursor.execute(u"SELECT DISTINCT BINARY name FROM genre WHERE id = BINARY %s", (track[5],))
                    genre = self.cursor.fetchall()[0][0]
                else:
                    genre = u""

                if track[7]:
                    self.cursor.execute(u"SELECT DISTINCT BINARY name FROM year WHERE id = BINARY %s", (track[7],))
                    year = self.cursor.fetchall()[0][0]
                else:
                    year = u""
                filename = track[0][1:]
                ret.append({'__filename': filename,
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
                            'track': unicode(track[9]),
                            'discnumber': unicode(track[10]),
                            '__bitrate': audioinfo.strbitrate(track[11] * 1000),
                            '__length': audioinfo.strlength(track[12]),
                            '__frequency': audioinfo.strfrequency(track[13]),
                            '__size': unicode(track[14]),
                            '___filetype': unicode(track[15]),
                            '___sampler': unicode(track[16]),
                            'bpm': unicode(track[17]),
                            '___deviceid': unicode(track[18]),
                            '__path': os.path.basename(filename),
                            '__ext': os.path.splitext(filename)[1][1:],
                            '__library': 'amarok'})
        return ret

    def _delTrack(self, track):
        self.cursor.execute('DELETE FROM tags WHERE url = %s', ("." + track[FILENAME],))

        for key in ('genre', 'year', 'album', 'composer', 'artist'):
            if self.cursor.execute('SELECT id FROM ' + key + ' WHERE name = BINARY %s', (track[key],)):
                keyid = self.cursor.fetchall()[0][0]
            if not self.cursor.execute('SELECT ' + key + ' FROM tags WHERE ' + key + ' = BINARY %s', (keyid,)):
                self.cursor.execute('DELETE FROM ' + key + ' WHERE id = %s', (keyid,))

    def delTracks(self, tracks):
        for track in tracks:
            self._delTrack(track)


    def saveTracks(self, tracks):
        dirname = os.path.dirname
        basename = os.path.basename
        freq = audioinfo.lngfrequency
        leng = audioinfo.lnglength
        converttag = audioinfo.converttag
        lngtime = audioinfo.lngtime

        for old, new in tracks:
            (old, new) = (converttag(old), converttag(new))
            mixed = old.copy()
            mixed.update(new)

            ids = {}
            for key in ('genre', 'year', 'album', 'composer', 'artist'):
                if self.cursor.execute('SELECT id FROM ' + key + ' WHERE name = BINARY %s', (new[key],)):
                    keyid = self.cursor.fetchall()[0][0]
                else:
                    self.cursor.execute('INSERT INTO ' + key + ' VALUES (NULL, %s)', (new[key], ))
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
                            freq(mixed["__frequency"]), long(mixed["__size"]),
                            mixed['___filetype'], mixed['___sampler'], mixed['bpm'],
                            mixed['___deviceid']))

            if old[FILENAME] != new[FILENAME]:
                self._delTrack(old)

class ConfigWindow(QWidget):
    def __init__(self, parent = None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Import Library")
        self.username = QLineEdit('amarok')
        self.passwd = QLineEdit()
        self.database = QLineEdit('amarok')
        self.passwd.setEchoMode(QLineEdit.Password)
        validator = QIntValidator(self)
        self.port = QLineEdit('3306')
        self.port.setValidator(validator)

        vbox = QVBoxLayout()
        [vbox.addWidget(z) for z in [QLabel('Username'), self.username,
            QLabel('Password'), self.passwd, QLabel('Database'),
            self.database, QLabel('port'), self.port]]
        vbox.addStretch()
        self.setLayout(vbox)

    def setStuff(self):
        username = unicode(self.username.text())
        passwd = unicode(self.passwd.text())
        database = unicode(self.database.text())
        port = long(self.port.text())

        try:
            return Amarok(user = username, passwd = passwd, db = database, port = port)
        except mysql.OperationalError, details:
            raise musiclib.LibLoadError, details

    def saveSettings(self):
        username = QVariant(self.username.text())
        passwd = QVariant(self.passwd.text())
        database = QVariant(self.database.text())
        port = QVariant(self.port.text())

        settings = QSettings()
        settings.beginGroup('Library')
        settings.setValue('username',username)
        settings.setValue('passwd', passwd)
        settings.setValue('database', database)
        settings.setValue('port', port)
        settings.endGroup()

    def loadSettings(self):
        settings.beginGroup('Library')
        self.username.setText(settings.value('username').toString())
        self.passwd.setText(settings.value('passwd').toString())
        self.database.setText(settings.value('database').toString())
        self.port.setText(settings.value('port').toString())
        settings.endGroup()

        return dict(user = username, passwd = passwd, db = database, port = port)

def loadLibrary():
    settings = QSettings()
    settings.beginGroup('Library')
    username = unicode(settings.value('username').toString())
    passwd = unicode(settings.value('passwd').toString())
    database = unicode(settings.value('database').toString())
    port = settings.value('port').toLongLong()[0]
    #try:
    return Amarok(user = username, passwd = passwd, db = database, port = port)
    #except mysql.OperationalError, details:
        #raise musiclib.LibLoadError, details


#if __name__ == "__main__":
    #db = Amarok(user = 'amarok', passwd = 'amarok', db = 'amarok')
    #artist = db.getArtists()[10]
    #i = db.getTracks(artist,db.getAlbums(artist))[0]
    #y = i.copy()
    #y[FILENAME] = './media/multi/Music/ktg.mp3'
    #db.saveTracks([(i,y)])