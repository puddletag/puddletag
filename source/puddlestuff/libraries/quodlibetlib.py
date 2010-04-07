# -*- coding: utf8 -*-
import sys, os, unittest, time, pdb, shutil
from os import path
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import cPickle as pickle
from puddlestuff.audioinfo.util import (FILENAME, DIRPATH, PATH, EXTENSION, READONLY,
                            FILETAGS, INFOTAGS, stringtags, getinfo, strlength,
                            MockTag, isempty, lngtime, lngfrequency,
                            lnglength, setdeco, getdeco)
import puddlestuff.audioinfo as audioinfo
ATTRIBUTES = ('bitrate', 'length', 'modified')
import quodlibet.config
from quodlibet.parse import Query
from functools import partial
from puddlestuff.constants import HOMEDIR


def strbitrate(bitrate):
    """Returns a string representation of bitrate in kb/s."""
    return unicode(bitrate/1000) + u' kb/s'

def strtime(seconds):
    """Converts UNIX time(in seconds) to more Human Readable format."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(seconds))


timetags = ['~#added', '~#lastplayed', '~#laststarted']
timefunc = lambda key: lambda value : {'__%s' % key[2:]: strtime(value)}
mapping = dict([(key, timefunc(key)) for key in timetags])

mapping.update({'tracknumber': lambda value: {'track': [value]},
                '~#bitrate' : lambda value: {'__bitrate': strbitrate(value)},
                '~#length': lambda value: {'__length': strlength(value)},
                '~#playcount': lambda value: {'_playcount': [unicode(value)]},
                '~#rating': lambda value: {'_rating': [unicode(value)]},
                '~#skipcount': lambda value: {'_skipcount': [unicode(value)]},
                '~mountpoint': lambda value: {'__mountpoint': value},
                '~#mtime': lambda value : {'__modified': strtime(value)},
                '~filename': lambda value : {'__path': value.decode('utf8')}})

timetags = ['__added', '__lastplayed', '__laststarted',]
timefunc = lambda key: lambda value : {'~#%s' % key[2:]: lngtime(value)}
revmapping = dict([(key, timefunc(key)) for key in timetags])
revmapping.update({'track': lambda value: {'tracknumber': value},
                '__bitrate' : lambda value: {'~#bitrate': lngfrequency(value)},
                '__length': lambda value: {'~#length': lnglength(value)},
                '_playcount': lambda value: {'~#playcount': long(value)},
                '_rating': lambda value: {'~#rating': float(value)},
                '_skipcount': lambda value: {'~#skipcount': long(value)},
                '__mountpoint': lambda value: {'~mountpoint': value},
                '__modified': lambda value : {'~#mtime': lngtime(value)},
                '__path': lambda value : {'~filename': value.encode('utf8')}})

class Tag(MockTag):
    """Use as base for all tag classes."""
    mapping = audioinfo.mapping['puddletag'] if 'puddletag' in audioinfo.mapping else {}
    revmapping = audioinfo.revmapping['puddletag'] if 'puddletag' in audioinfo.revmapping else {}
    IMAGETAGS = ()
    _hash = {PATH: 'filepath',
            FILENAME:'filename',
            EXTENSION: 'ext',
            DIRPATH: 'dirpath'}
    def __init__(self, libclass, libtags):
        MockTag.__init__(self)
        self.library = libclass
        self.remove = partial(libclass.delete, track=libtags)
        self._libtags = libtags
        tags = {}
        for key, value in libtags.items():
            if key in mapping:
                tags.update(mapping[key](value))
            else:
                tags[key] = [value]
        self._tags = tags
        self._set_attrs(ATTRIBUTES)
        self.filepath = tags[PATH]
        info = getinfo(self.filepath)
        self.size = info['__size']
        self._tags['__size'] = self.size
        self.accessed = info['__accessed']
        self._tags['__accessed'] = self.accessed

    def _getfilepath(self):
        return self._tags[PATH]

    def _setfilepath(self,  val):
        self._libtags['~filename'] = val.encode('utf8')
        self._tags.update({PATH: val,
                           DIRPATH: path.dirname(val),
                           FILENAME: path.basename(val),
                           EXTENSION: path.splitext(val)[1][1:]})

    filepath = property(_getfilepath, _setfilepath)

    @getdeco
    def __getitem__(self, key):
        if key in self._tags:
            return self._tags[key]
        return ['']

    @setdeco
    def __setitem__(self, key, value):
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
            self._tags[key] = [unicode(value)]
        else:
            self._tags[key] = [unicode(z) for z in value]

    def save(self, justrename = False):
        if justrename:
            return
        self._libtags.update(self._tolibformat())
        self._libtags.write()

    def sget(self, key):
        return self[key] if self.get(key) else ''

    def _tolibformat(self):
        libtags = {}
        tags = stringtags(self._tags).items()
        for key, value in tags:
            if key in revmapping:
                libtags.update(revmapping[key](value))
            elif key in INFOTAGS:
                continue
            else:
                libtags[key] = value
        if '__accessed' in libtags:
            del(libtags['__accessed'])

        if '__size' in libtags:
            del(libtags['__size'])
        return libtags


class Tests(unittest.TestCase):
    def setUp(self):
        self._lib = QuodLibet('/home/keith/.quodlibet/songs')

    def templib(self):
        if not os.path.exists('songs.test'):
            shutil.copy('/home/keith/.quodlibet/songs', 'songs.test')
        return QuodLibet('songs.test')

    def remove_templib(self):
        os.remove('songs.test')

    def test_getartist(self):
        tracks = self._lib.get_tracks('artist', u'Alicia Keys')
        self.failIf(not tracks)
        self.failIf([z for z in tracks if z['artist'] != [u'Alicia Keys']])

    def test_getalbum(self):
        tracks = self._lib.get_tracks('artist', u'Alicia Keys', 'album', 'As I Am')
        self.failIf(not tracks)
        self.failIf([z for z in tracks if z['artist'] != [u'Alicia Keys']
                     or z['album'] != [u'As I Am']])

    def test_getunicode(self):
        artist = u'редислови'
        album = u'Felony'
        tracks = self._lib.get_tracks('artist', artist)
        self.failIf(not tracks)
        self.failIf([z for z in tracks if z['artist'] != [artist]])

        tracks = self._lib.get_tracks('artist', artist, 'album', album)
        self.failIf(not tracks)
        self.failIf([z for z in tracks if z['artist'] != [artist]
                     and z['album'] != [album]])

    def test_convert(self):
        ['album', 'artist', 'date', 'discnumber', 'performer', 'title', 'tracknumber', '~#added', '~#bitrate', '~#lastplayed', '~#laststarted', '~#length', '~#mtime', '~#playcount', '~#rating', '~#skipcount', '~filename', '~mountpoint']

        track = self._lib.get_tracks('artist', u'Alicia Keys')[0]

        #self.failIf({'album': [u'As I Am'], '_skipcount': [u'0'], '__ext': 'mp3', 'performer': [u'Alicia Keys'], '_playcount': [u'0'], 'title': [u'As I Am (Intro)'], '__bitrate': u'256 kb/s', u'__filename': 'Alicia Keys - 01 - As I Am (Intro).mp3', 'artist': [u'Alicia Keys'], '__length': u'0 kb/s', '_rating': [u'0.5'], 'track': [u'1'], '__added': '2010-04-02 20:50:22', '__dirpath': '/mnt/home/storage/puddle/Alicia Keys - As I Am.backup', '__modified': '2010-04-02 19:26:34', '__path': '/mnt/home/storage/puddle/Alicia Keys - As I Am.backup/Alicia Keys - 01 - As I Am (Intro).mp3', 'date': [u'2007'], '__mountpoint': '/mnt/home', 'discnumber': [u'1 / 1'], '__lastplayed': '1970-01-01 00:00:00', '__laststarted': '1970-01-01 00:00:00'} != track.tags)

        filename = track[PATH]
        self.assertEqual(track.filepath, filename)
        self.assertEqual(track.filename, os.path.basename(filename))
        self.assertEqual(track.dirpath, os.path.dirname(filename))
        self.assertEqual(track.ext, os.path.splitext(filename)[1][1:])
        assert track.modified
        assert track.bitrate
        assert track.accessed

        track = self._lib._tracks[0]
        tag = Tag(self._lib, track)
        assert sorted(tag._tolibformat().items()) == sorted(track.items())


    def test_distinct(self):
        artists  = sorted([u'2 Live Crew', u'A Tribe Called Quest', u'Afrika Bambatta', u'Alicia Keys', u'Beastie Boys', u'Beyonce', u'Beyonc\xe9', u'Big Daddy Kane', u'Big Punisher', u'Biz Markie', u'Bob Marley & The Wailers', u'Boogie Down Productions', u'Busta Rhymes', u"Cam'ron", u'Common', u'Coolio', u'Digable Planets', u'Digital Underground', u'Dj Jazzy Jeff & The Fresh Prince', u'Eminem', u'Emmure', u'Emmure\u0627\u0644\u0645\u0644\u0641', u'Eric B. & Rakim', u'Geto Boys', u'Goodie Mob', u'Grandmaster Flash', u'Ice T', u'Juvenile', u'LL Cool J', u'Lauryn Hill', u'Ludacris', u'Luniz', u'Mary J. Blige', u'Mc Hammer', u'Missy Elliott', u'Mobb Deep', u'N.W.A.', u'Nas', u'Naughty By Nature', u'Nelly', u'Notorious B.I.G', u'OutKast', u'Public Enemy', u'Puff Daddy', u'Queen Latifah', u'Ratatat', u'Run D.M.C.', u'Run D.M.C. & Aerosmith', u'Salt N Pepa', u'Skee Lo', u'Slick Rick', u'Styles P', u'The Fugees', u'The Sugarhill Gang', u'Tone Loc', u'Twista', u'Wu Tang Clan', u'Young Mc', u'concentricpuddle', u'\u0440\u0435\u0434\u0438\u0441\u043b\u043e\u0432\u0438'])
        self.assertEqual(sorted(self._lib.distinct_values('artist')), artists)
        albums = ['', u'9 Beats', u'ATLiens', u'As I Am', u'As I Am (The Super Edition)', u'Babylon By Bus', u'Classics', u'Dangerously In Love', u'Dj Finesse Certified Rnb King', u"Don't Call Me Marshall", u'Felony', u'I Am ... Sasha Firece (Platinum Edition)', u'I Am... Sasha Fierce (Disc 1)', u'I Am... Sasha Fierce (Disc 2)', u'I Am...Sasha Fierce', u'LP3', u'No One (Remixes)', u'Promo Only Urban Radio October', u'Ratatat', u'Ratatat Remixes Vol. 1', u'Ratatat Remixes Vol. 2', u'Remixes', u'So Amazing - An All Star Tribute To Luther Vandross', u'The Element Of Freedom', u'The Element Of Freedom (Bonus Tracks)', u'The Fighting Temptations', u'Unknown', u'Unknown Album (1/9/2004 4:25:09 Pm)', u'Unplugged', u'Www.Mzhiphop.Com', u'[Www.Usfmusic.Wordpress.Com]', u'\u0440\u0435\u0434\u0438\u0441\u043b\u043e\u0432\u0438', u'\u0627\u0644\u0645\u0644\u0641<']
        self.assertEqual(sorted(self._lib.distinct_values('album')), albums)

    def test_distinct_children(self):
        lib = self._lib
        children = [u'As I Am', u'As I Am (The Super Edition)', u'No One (Remixes)', u'The Element Of Freedom', u'The Element Of Freedom (Bonus Tracks)', u'Unplugged']
        self.assertEqual(sorted(lib.distinct_children('artist',
                            "Alicia Keys", 'album')), children)

        titles = [u'(Girl) I Love You', u"A Woman's Worth (Live)", u'After Laughter (Comes Tears)', u'Another Way To Die', u'As I Am (Intro)', u'Diary', u'Distance And Time', u"Doesn't Mean Anything", u'Doncha Know (Sky Is Blue)', u'Empire State Of Mind (Part II) Broken Down', u'Every Little Bit Hurts', u"Fallin'", u'Go Ahead', u'Heartburn', u"How Come You Don't Call Me", u'How It Feels To Fly', u'I Need You', u"If I Ain't Got You", u'If I Was Your Woman', u"Intro Alicia's Prayer (Acappella)", u'Karma', u'Lesson Learned', u'Lesson Learned ft John Mayer', u'Like The Sea', u"Like You'll Never See Me Again", u"Like You'll Never See Me Again - Main", u'Love Is Blind', u'Love Is My Disease', u'Love It Or Leavewelcome To Jamrock with Mos Def, Common, Damien Marley And Friends', u'No One', u'No One (Hip Hop Remix) ft Cassidy', u'No One (Manny Faces Remix)', u'No One (Reggae Remix) ft Junior Reid', u'No One (Urban Noize Remix)', u'Pray For Forgiveness', u'Prelude To A Kiss', u'Put It In A Love Song (featuring Beyonce)', u'Saviour', u'Stolen Moments', u'Streets Of New York (City Life)', u'Superwoman', u'Sure Looks Good To Me', u'Teenage Love Affair', u"Tell You Something (Nana's Reprise)", u"That's How Strong My Love Is", u'The Element Of Freedom (Intro)', u'The Thing About Love', u'This Bed', u'Through It All', u'Try Sleeping With A Broken Heart', u"Un-Thinkable (I'm Ready) (featuring Drake)", u'Unbreakable', u'Wait Til You See My Smile', u'Where Do We Go From Here', u'Wild Horses ft Adam Levine', u'Wreckless Love', u"You Don't Know My Name"]
        self.assertEqual(sorted(lib.distinct_children('artist',
                            "Alicia Keys", 'title')), titles)

    def test_write(self):
        lib = self.templib()
        import random
        value = unicode(random.random())

        track = lib.get_tracks('artist', u'Alicia Keys')[0]
        track['artist'] = [value]
        track.save()

        self.failIf(value not in lib.artists)
        lib.save()
        lib = self.templib()
        self.remove_templib()
        self.failIf(value not in lib.artists)
        self.failUnless(lib.get_tracks('artist', value))

    def test_delete(self):
        lib = self.templib()
        tracks = lib.get_tracks('artist', u'Alicia Keys')
        [track.remove() for track in tracks]
        self.failIf(lib.get_tracks('artist', u'Alicia Keys'))
        lib.save()

        lib = self.templib()
        self.remove_templib()
        self.failIf(lib.get_tracks('artist', u'Alicia Keys'))

    def test_mapping(self):
        tag = self._lib.get_tracks('artist', u'Alicia Keys')[0]
        mapping = {'artist': 'title',
                   'title': 'artist'}
        artist = tag['artist']
        title = tag['title']

        tag.mapping = mapping
        tag.revmapping = mapping

        self.assertEqual(tag['artist'], title)
        self.assertEqual(tag['title'], artist)


class QuodLibet(object):
    def __init__(self, filepath, config = None):
        self._tracks = pickle.load(open(filepath, 'rb'))
        if not config:
            config = os.path.join(os.path.dirname(filepath), u'config')
        try:
            quodlibet.config.init(config)
        except ValueError:
            "Raised if this method's called twice."
        self._filepath = filepath

    def get_tracks(self, maintag, mainval, secondary=None, secvalue=None):
        if secondary and secvalue:
            def getvalue(track):
                return (track.get(maintag) == mainval) and (
                        track.get(secondary) == secvalue)
        else:
            def getvalue(track):
                return (track.get(maintag) == mainval)

        return [Tag(self, track) for i, track in enumerate(self._tracks)
                if getvalue(track)]

    def distinct_values(self, tag):
        return set([track[tag] if tag in track else '' for track in self._tracks])

    def distinct_children(self, tag, value, childtag):
        return set([track[childtag] if childtag in track else '' for track in
                    self._tracks if (tag in track) and (track[tag] == value)])

    def _artists(self):
        return self.distinct_values('artist')

    artists = property(_artists)

    def get_albums(self, artist):
        return self.distinct_children('artist', artist, 'album')

    def save(self):
        pickle.dump(self._tracks, open(self._filepath, 'wb'))

    def delete(self, track):
        self._tracks.remove(track)

    def tree(self):
        title = 'title'
        for artist in self.artists:
            print artist
            albums = self.get_albums(artist)
            for album in albums:
                print u'  ', album
                tracks = self.get_tracks('artist', artist, 'album', album)
                for track in tracks:
                    print u'      ', track[title][0] if title in track else u''

    def close(self):
        pass

    def search(self, text):
        try:
            filt = Query(text).search
        except Query.error:
            return []
        else:
            return [Tag(self, track) for track in filter(filt, self._tracks)]

class InitWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.dbpath = QLineEdit(os.path.join(HOMEDIR, u".quodlibet/songs"))
        self.configpath = QLineEdit(os.path.join(HOMEDIR, u".quodlibet/config"))

        vbox = QVBoxLayout()
        def label(text, control):
            l = QLabel(text)
            l.setBuddy(control)
            return l

        vbox.addWidget(label('&Library Path', self.dbpath))

        hbox = QHBoxLayout()
        select_db = QPushButton("...")
        self.connect(select_db, SIGNAL('clicked()'), self.select_db)
        hbox.addWidget(self.dbpath)
        hbox.addWidget(select_db)
        vbox.addLayout(hbox)

        vbox.addStretch()
        vbox.addWidget(label('&Config Path', self.configpath))

        hbox = QHBoxLayout()
        select_config = QPushButton("...")
        self.connect(select_config, SIGNAL('clicked()'), self.select_config)
        hbox.addWidget(self.configpath)
        hbox.addWidget(select_config)
        vbox.addLayout(hbox)

        vbox.addStretch(1)
        self.setLayout(vbox)
        self.dbpath.selectAll()
        self.configpath.selectAll()
        self.dbpath.setFocus()

    def select_db(self):
        filedlg = QFileDialog()
        filename = filedlg.getOpenFileName(self,
            'Select Quodlibet database file.', self.dbpath.text())
        if filename:
            self.dbpath.setText(filename)

    def select_config(self):
        filedlg = QFileDialog()
        filename = filedlg.getOpenFileName(self,
            'Select Quodlibet config file.', self.configpath.text())
        if filename:
            self.configpath.setText(filename)

    def library(self):
        dbpath = unicode(self.dbpath.text())
        configpath = unicode(self.configpath.text())
        return QuodLibet(dbpath, configpath)

name = u'Quodlibet'

if __name__ == '__main__':
    unittest.main()
    #QuodLibet('songs').tree()
    #print QuodLibet('songs').search("Alicia Keys")
    #app = QApplication([])
    #win = ConfigWindow()
    #win.show()
    #app.exec_()
