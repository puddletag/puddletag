"""An example tag source plugin for puddletag.

It answers from the albums listed below instead of a web service, so it
works as soon as it's installed: extract this folder into puddletag's
plugins folder (~/.local/share/puddletag/plugins), tick Example Tag
Source in Edit->Preferences->Plugins and restart puddletag. In the Tag
Sources window pick Example Source, select files whose album is First
Album or Second Album and click Search.

puddletag imports a plugin as puddlestuff.plugins.<folder name> and
loads the tag sources listed in tagsources, at the bottom of this file.
"""
from puddlestuff.constants import CHECKBOX, COMBO, SPINBOX, TEXT
from puddlestuff.tagsources import RetrievalError, parse_searchstring, write_log

# A tag source on the web downloads its data. If you're retrieving urls
# use puddlestuff.tagsources.urlopen instead of the generic urllib
# functions: it sends puddletag's user agent and turns every failure
# into a RetrievalError. Pass it your url and it'll return your data.

# Raise puddlestuff.tagsources.RetrievalError if an error occurs. It
# accepts a message as its only argument (may be html), which the Tag
# Sources window shows.

# Write to puddletag's Logs window with write_log(text).

# Covers: an album's info or a track may hold '__image', a list of
# dictionaries with the following keys (all from puddlestuff.audioinfo):
# DATA: Required. The image's data.
# MIMETYPE: either 'image/jpeg' or 'image/png'.
# DESCRIPTION: the image's description.
# IMAGETYPE: index of the element corresponding to audioinfo.IMAGETYPES.

ALBUMS = [
    {'#id': 'first', 'album': 'First Album', 'artist': 'Example Artist', 'year': '2001',
     '#extrainfo': ('The album on the web', 'https://example.com/first-album')},
    {'#id': 'second', 'album': 'Second Album', 'artist': 'Example Artist', 'year': '2004'},
]

TRACKS = {
    'first': [{'title': 'Opening', 'track': '1'}, {'title': 'Middle', 'track': '2'},
              {'title': 'Closing', 'track': '3'}],
    'second': [{'title': 'Again', 'track': '1'}, {'title': 'Encore', 'track': '2'}],
}


class ExampleSource:
    # Required: the name shown in the Tag Sources window and in the
    # Source box of a Mass Tagging profile.
    name = 'Example Source'

    # How puddletag groups the selected files before calling search():
    # here by album first, then by artist. search() then gets an album
    # (a string) and a dictionary whose keys are that album's artists
    # and whose values are each artist's files. Each file is dict-like,
    # eg. {'track': ['10'], 'title': ['Natural Anthem'], '__length': '5:07'}:
    # values are usually lists and "builtin" values are strings.
    # With group_by = None, search() gets the selected files themselves
    # instead: search(self, files).
    group_by = ['album', 'artist']

    def __init__(self):
        # __init__ should not accept any arguments.

        # preferences is a list of lists defining the controls of the
        # Tag Source's config dialog (Configure, in the Tag Sources
        # window). Each holds three items:
        # 1. Some descriptive text that's shown in a label.
        # 2. The control type: TEXT, COMBO, CHECKBOX or SPINBOX, for a
        #    QLineEdit, QComboBox, QCheckBox or QSpinBox.
        # 3. The default, which is required:
        #    TEXT: the default text, '' for an empty box.
        #    COMBO: a list of the items' texts, and the default index,
        #    eg. [['text1', 'text2'], 1].
        #    CHECKBOX: True (ticked) or False.
        #    SPINBOX: the minimum, the maximum and the default, eg.
        #    [0, 100, 80].
        # Leave preferences out for a source with nothing to configure:
        # the Configure button is then hidden.
        self.preferences = [
            ['Retrieve the year', CHECKBOX, True],
            ['Titles', COMBO, [['As listed', 'Upper case'], 0]],
            ['Genre to add', TEXT, ''],
            ['Tracks to retrieve at most', SPINBOX, [1, 99, 99]],
        ]
        self.year, self.upper, self.genre, self.most = True, 0, '', 99

    def applyPrefs(self, values):
        # Called when puddletag starts, with the saved values (the
        # defaults until the user changes them), and when the user has
        # finished editing and clicks OK. values is a list in the order
        # the controls were defined: True or False for CHECKBOX, the
        # text for TEXT, the selected index for COMBO and the number for
        # SPINBOX.
        self.year, self.upper, self.genre, self.most = values

    def keyword_search(self, text):
        # Searches for what the user typed in the Search box. This
        # method is optional, but recommended: without it the Search box
        # is disabled.
        # The format artist1;album1|artist2;album2 should be accepted.
        # Use the parse_searchstring method to separate text into a list
        # of artist album pairs as in: [(artist1, album1), (artist2, album2)]
        found = []
        for artist, album in parse_searchstring(text):
            found.extend(self.search(album, {artist: []}))
        return found

    def search(self, album, artists):
        # Required. Returns a list of (album info, tracks) pairs.
        # Album info is a dictionary of the fields of the whole album,
        # eg. {'artist': 'The Postal Service', 'album': 'Give Up',
        # 'year': '2003'}; values can be strings or lists of strings.
        # Any key starting with '#' is the source's own and is never
        # written to a file: keep in them what retrieve() needs, like an
        # id. '#extrainfo', a (text, address) pair, is shown as a link
        # when the user picks the album.
        # Return (info, []) when the tracks need another lookup:
        # retrieve() gets them when the user picks the album. Return the
        # tracks too when the search already has them.
        write_log(f'Example Source: searching for {album}')
        if not album:
            raise RetrievalError('<b>The files have no album to search for.</b>')
        return [(dict(info), []) for info in ALBUMS if info['album'].lower() == album.lower()]

    def retrieve(self, info):
        # Required. Gets the album's tracks with the info search()
        # returned. Returns the album's info (a second lookup may find
        # more) and its tracks: one dictionary per track, in the
        # album's order, eg. [{'title': 'The District Sleeps Alone
        # Tonight', 'track': '1'}, {'title': 'Such Great Heights',
        # 'track': '2'}].
        info = dict(info)
        if not self.year:
            info.pop('year', None)
        tracks = [dict(track) for track in TRACKS[info['#id']][:self.most]]
        for track in tracks:
            if self.upper:
                track['title'] = track['title'].upper()
            if self.genre:
                track['genre'] = self.genre
        return info, tracks

    # Optional: submit(self, files) adds a Submit button to the Tag
    # Sources window, as AcoustID has.


# Required in order to let your tag source be loaded: the classes, not
# instances of them. One plugin can hold several tag sources.
tagsources = [ExampleSource]
