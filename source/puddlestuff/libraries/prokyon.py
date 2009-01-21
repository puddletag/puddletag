import MySQLdb as mysql
import sys, os, pdb
sys.path.insert(1, os.path.dirname(os.path.dirname(__file__)))
import audioinfo, pdb
from operator import itemgetter
FILENAME = audioinfo.FILENAME
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from mutagen.id3 import TCON
GENRES = TCON.GENRES

name = "Prokyon"
description = "Prokyon Database"
author = 'concentricpuddle'

class Prokyon:
    def __init__(self, **keywords):
        keywords['use_unicode'] = True
        keywords['charset'] = 'utf8'
        self.db = mysql.connect(**keywords)
        self.cursor = self.db.cursor()

    def getArtists(self):
        self.cursor.execute(u"SELECT DISTINCT BINARY artist FROM tracks ORDER BY artist")
        artists = self.cursor.fetchall()
        return [z[0] for z in artists]

    def getAlbums(self, artist):
        self.cursor.execute(u"SELECT DISTINCT BINARY album FROM tracks WHERE artist = BINARY %s", (artist,))
        albums = [z[0] for z in self.cursor.fetchall()]
        return albums

    def getTracks(self, artist, albums):
        join = os.path.join
        ret = []
        for album in albums:
            self.cursor.execute(u"""SELECT path, filename, bitrate, samplerate,
                                length, title, tracknumber, year, genre, comment,
                                size, lastModified, layer, mimetype, version,
                                mode FROM tracks WHERE artist = BINARY %s
                                AND album = BINARY %s""", (artist, album))
            tracks = (self.cursor.fetchall())
            for track in tracks:
                try:
                    genre = GENRES[track[8]]
                except (IndexError, TypeError):
                    genre = u''
                ret.append({'__filename': join(track[0], track[1]),
                    '__path': track[1],
                    '__ext': os.path.splitext(track[1])[1][1:], #Don't need(or want) the extra dot
                    '__bitrate': audioinfo.strbitrate(track[2] * 1000),
                    '__frequency': audioinfo.strfrequency(track[3]),
                    '__length': audioinfo.strlength(track[4]),
                    '__folder': track[0],
                    'title': track[5],
                    'track': unicode(track[6]),
                    'year': unicode(track[7]),
                    'genre': genre,
                    'comment': track[9],
                    '__size' : unicode(track[10]),
                    '__modified': unicode(track[11]),
                    'artist': artist,
                    'album': album,
                    '__library': 'prokyon',
                    "___layer": track[12],
                    '___mimetype': track[13],
                    '___version': track[14]})
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
                    self.cursor.execute('''UPDATE artists SET total = %s,
                        local = %s WHERE id = %s''', (tks - 1, tks - 1, fileid))

            album = track['album'][0]
            if self.cursor.execute('''SELECT id, tracks_available FROM albums
                WHERE artist = BINARY %s AND name = BINARY %s''', (artist, album)):
                (fileid, tks) = self.cursor.fetchall()[0]
                if tks > 1:
                    self.cursor.execute('UPDATE albums SET tracks_available = %s WHERE id = %s', (tks - 1, fileid))
                else:
                    self.cursor.execute('DELETE FROM albums WHERE id = %s', (fileid,))

    def saveTracks(self, tracks):
        dirname = os.path.dirname
        basename = os.path.basename
        freq = audioinfo.lngfrequency
        leng = audioinfo.lnglength
        converttag = audioinfo.converttag
        def genretoint(genre):
            try:
                return GENRES.index(genre)
            except ValueError:
                return 255

        for old, new in tracks:
            (old, new) = (converttag(old), converttag(new))
            mixed = old.copy()
            mixed.update(new)
            oldfilename = basename(old['__filename'])
            oldpath = dirname(old['__filename'])

            newfilename = basename(new['__filename'])
            newpath = dirname(new['__filename'])
            #Check if the new file exists in the table, delete the row if it does
            #since filenames have to be unique.
            if self.cursor.execute('SELECT id FROM tracks WHERE path = BINARY %s AND filename = BINARY %s', (newpath, newfilename)):
                fileid = self.cursor.fetchall()[0][0]
                self.cursor.execute('DELETE FROM tracks WHERE id = %s', (fileid,))

            #Update the old file if it exists. Create new one otherwise.
            if self.cursor.execute('SELECT id FROM tracks WHERE path = BINARY %s AND filename = BINARY %s', (oldpath, oldfilename)):
                fileid = self.cursor.fetchall()[0][0]
            else:
                self.cursor.execute('SELECT MAX(id) FROM tracks')
                fileid = self.cursor.fetchall()[0][0] + 1

            self.cursor.execute("""REPLACE INTO tracks VALUES
                            (%s, %s, %s, 0, %s,
                            0, %s, %s, %s ,0,
                            %s, %s, %s, %s,
                            %s, %s,NULL, %s, %s,
                            %s, %s, %s, NULL,3)""",
                            (fileid, newpath, newfilename, mixed['__modified'],
                            mixed['___mimetype'], mixed['___version'], mixed['___layer'],
                            freq(mixed['__bitrate']) / 1000, freq(mixed["__frequency"]), leng(mixed["__length"]), long(mixed["__size"]),
                            mixed["artist"], mixed["title"], mixed['album'], mixed['track'],
                            mixed['year'], genretoint(mixed['genre']), mixed["comment"]))

            #Update artists table
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

            #Update albums table.
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

class ConfigWindow(QWidget):
    def __init__(self, parent = None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Import Library")
        self.username = QLineEdit('root')
        self.passwd = QLineEdit()
        self.database = QLineEdit('prokyon')
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

        return Prokyon(user = username, passwd = passwd, db = database, port = port)

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
    return Prokyon(user = username, passwd = passwd, db = database, port = port)


if __name__ == "__main__":
    db = Prokyon(user = 'root', passwd = 'ktgisgreat', db = 'prokyon')
    albums = db.getTracks('101', [db.getAlbums('101')[0]])
    db.saveTracks([(albums[0],{'artist': '102 well, who else'})])