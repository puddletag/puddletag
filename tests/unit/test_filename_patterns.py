"""File->Tag and Tag->File, called the way mainwin/funcs.py calls them.

Expected results come from docsrc/source/menus.txt (File->Tag),
function.txt ("Tag to filename") and tut1.txt with its screenshots, or from
the linked reports. Folders and tag values that a source doesn't give are
synthetic.
"""
import os

import pytest

from puddlestuff import audioinfo, functions
from puddlestuff.findfunc import filenametotag


def file_to_tag(pattern, path):
    # The extension is left out of the match (checkext).
    return filenametotag(pattern, path, True)


@pytest.fixture
def tag_to_file(make_audio, tmp_path):
    """Run Tag->File on a new file at path (under tmp_path) with these tags.

    Returns the new path, relative to tmp_path if it's inside it.
    """
    def run(pattern, path, **tags):
        native = {('tracknumber' if key == 'track' else key): value for key, value in tags.items()}
        audio = audioinfo.Tag(str(make_audio(os.path.basename(path), tmp_path / os.path.dirname(path), **native)))
        new_path = functions.move(audio, pattern, audio, state={'__counter': '1', '__total_files': '1'})['__path']
        return new_path.removeprefix(str(tmp_path) + os.sep)
    return run


@pytest.mark.parametrize('pattern, path, expected', [
    # menus.txt
    ('%artist% - %title%', '/music/Indie Artist - No Autotune.mp3',
     {'artist': 'Indie Artist', 'title': 'No Autotune'}),
    ('%artist%#%title%#%track%', '/music/Wanton_character_#_something_irreligious#01',
     {'artist': 'Wanton_character_', 'title': '_something_irreligious', 'track': '01'}),
    ('%title% - %dummy%', "/music/I love autotune - Artist Doesn't Matter.mp3",
     {'title': 'I love autotune'}),
    ('%artist% - %album%/%track% - %title%',
     '/home/cpuddle/Music/Justin Bieber - Dunno/01 - Kinda Terrible.mp3',
     {'artist': 'Justin Bieber', 'album': 'Dunno', 'track': '01', 'title': 'Kinda Terrible'}),
    ('%artist%/%album%/%track% - %title%',
     "/home/cpuddle/Music/Freshlyground/Nomvula/06 - I'd Like.mp3",
     {'artist': 'Freshlyground', 'album': 'Nomvula', 'track': '06', 'title': "I'd Like"}),
    ('%artist% - %album%/%dummy%',
     '/home/cpuddle/Music/Justin Bieber - Dunno/01 - Kinda Terrible.mp3',
     {'artist': 'Justin Bieber', 'album': 'Dunno'}),
    # tut1.txt, and its status bar in tut1/3full.png
    ('%artist% - %track% - %title%',
     '/mnt/home/storage/puddle/Bob Marley - Babylon By Bus/Bob Marley & The Wailers - 01 - Positive Vibration.mp3',
     {'artist': 'Bob Marley & The Wailers', 'track': '01', 'title': 'Positive Vibration'}),
])
def test_documented_file_to_tag(pattern, path, expected):
    assert file_to_tag(pattern, path) == expected


@pytest.mark.parametrize('pattern, path, expected', [
    pytest.param(  # the reporter's single-disc layout
        '%genre%/%artist%/%year% - %album%/%track% - %title%',
        '/audio/genre/artist/Year - Album/01 - The First Song.mp3',
        {'genre': 'genre', 'artist': 'artist', 'year': 'Year', 'album': 'Album',
         'track': '01', 'title': 'The First Song'},
        id='I460-single-disc'),
    pytest.param(  # and their multi-disc one
        '%genre%/%artist%/%year% - %album%/%discnumber%_%track% - %title%',
        '/audio/genre/artist/Year - Album/1_01 - The First Song on CD1.mp3',
        {'genre': 'genre', 'artist': 'artist', 'year': 'Year', 'album': 'Album',
         'discnumber': '1', 'track': '01', 'title': 'The First Song on CD1'},
        id='I460-multi-disc'),
    pytest.param(  # a saved pattern in github.com/xeruf/dotfiles .config/puddletag/puddletag.conf; synthetic filename
        '%track% %artist% - %title%', '/music/01 Some Artist - Title.mp3',
        {'track': '01', 'artist': 'Some Artist', 'title': 'Title'},
        id='xeruf-dotfiles'),
])
def test_shared_file_to_tag(pattern, path, expected):
    assert file_to_tag(pattern, path) == expected


@pytest.mark.xfail(strict=True, reason='File->Tag matches $num(...) as literal text, so the pattern matches nothing (#210)')
def test_file_to_tag_with_a_function():
    # The first of the Pattern Combo's default patterns
    # (mainwin/patterncombo.py), which Tag->File handles. Synthetic filename.
    tags = file_to_tag('%artist% - $num(%track%,2) - %title%', '/music/Artist - 01 - Title.mp3')
    assert (tags.get('artist'), tags.get('title')) == ('Artist', 'Title')


BEFORE_THE_FAME = {'artist': 'Before The Fame', 'album': 'The Vinyl LP',
                   'title': 'Sounds Better Than Anything After', 'track': '10'}
UNKNOWN_PATH = 'home/concentricpuddle/multimedia/music/Indie/unsorted/unknown.mp3'
UNKNOWN = {'artist': 'Relatively Unknown', 'title': 'Horrible for everyone else',
           'album': 'Fans like it', 'track': '5'}
BOB_MARLEY_PATH = 'mnt/home/storage/puddle/Bob Marley - Babylon By Bus/01 - Positive Vibration.mp3'
BOB_MARLEY = {'artist': 'Bob Marley & The Wailers', 'title': 'Positive Vibration', 'track': '01'}


@pytest.mark.parametrize('pattern, path, tags, expected', [
    # function.txt, "Tag to filename". It gives the file's name, not its folder.
    ('%artist% - %album% - %title%', 'music/track.mp3', BEFORE_THE_FAME,
     'music/Before The Fame - The Vinyl LP - Sounds Better Than Anything After.mp3'),
    ('%artist% - $num(%track%, 3) - %title%', 'music/track.mp3', BEFORE_THE_FAME,
     'music/Before The Fame - 010 - Sounds Better Than Anything After.mp3'),
    ('%title%_$upper(%album%)-%track%-%artist%', 'music/track.mp3', BEFORE_THE_FAME,
     'music/Sounds Better Than Anything After_THE VINYL LP-10-Before The Fame.mp3'),
    # "For every slash, the file is moved up one directory."
    ('%album%/%artist% - %title%', UNKNOWN_PATH, UNKNOWN,
     'home/concentricpuddle/multimedia/music/Indie/Fans like it/Relatively Unknown - Horrible for everyone else.mp3'),
    ('%artist%/%album%/%title%', UNKNOWN_PATH, UNKNOWN,
     'home/concentricpuddle/multimedia/music/Relatively Unknown/Fans like it/Horrible for everyone else.mp3'),
    ('/mnt/library/%album%/%track%', UNKNOWN_PATH, UNKNOWN, '/mnt/library/Fans like it/5.mp3'),
    # "if the artist is AC/DC, it will not create an AC directory"
    ('%artist%/%title%', UNKNOWN_PATH, dict(UNKNOWN, artist='AC/DC'),
     'home/concentricpuddle/multimedia/music/Indie/ACDC/Horrible for everyone else.mp3'),
    # The characters it removes; synthetic title.
    ('%title%', 'music/track.mp3', {'title': 'a\\b*c?d"e|f:g/h;i'}, 'music/abcdefgh;i.mp3'),
    # "A directory that comes out empty is left out"
    ('/mnt/music/%album%/$if(%discnumber%,Disc %discnumber%,)/%title%', 'music/track.mp3',
     dict(BEFORE_THE_FAME, discnumber='1'),
     '/mnt/music/The Vinyl LP/Disc 1/Sounds Better Than Anything After.mp3'),
    ('/mnt/music/%album%/$if(%discnumber%,Disc %discnumber%,)/%title%', 'music/track.mp3',
     BEFORE_THE_FAME, '/mnt/music/The Vinyl LP/Sounds Better Than Anything After.mp3'),
    # tut1.txt, with the patterns and new names in tut1/5full.png and 6full.png
    ('$num(%track%,2) - %title%', BOB_MARLEY_PATH, BOB_MARLEY,
     'mnt/home/storage/puddle/Bob Marley - Babylon By Bus/01 - Positive Vibration.mp3'),
    ('$num(%track%, 1) - %title%', BOB_MARLEY_PATH, BOB_MARLEY,
     'mnt/home/storage/puddle/Bob Marley - Babylon By Bus/1 - Positive Vibration.mp3'),
])
def test_documented_tag_to_file(tag_to_file, pattern, path, tags, expected):
    assert tag_to_file(pattern, path, **tags) == expected


ARTIST_IF_NOT_ALBUMARTIST = (r'$if(%discnumber%, %discnumber% - ,)$num(%track%,2) - %title%'
                             r'$if($replace(%artist%, %albumartist%,),\ - %artist%,)')
DISC_FOLDERS = ('/mnt/data/music/%albumartist%/%album%/'
                '$if($grtr(%disctotal%,1),Disc %discnumber%,.)/$num(%track%,2) - %title%')
ALBUM = {'albumartist': 'Band', 'album': 'Album', 'discnumber': '1', 'track': '3', 'title': 'Song'}


@pytest.mark.parametrize('pattern, path, tags, expected', [
    pytest.param(  # the working pattern from the issue's last comment. Its
        # "\ " keeps the space: Tag->File removes the backslash.
        ARTIST_IF_NOT_ALBUMARTIST, 'music/x.flac', dict(ALBUM, artist='Guest'),
        'music/1 - 03 - Song - Guest.flac',
        id='I664-other-artist'),
    pytest.param(
        ARTIST_IF_NOT_ALBUMARTIST, 'music/x.flac', dict(ALBUM, artist='Band'),
        'music/1 - 03 - Song.flac',
        id='I664-same-artist'),
    pytest.param(
        ARTIST_IF_NOT_ALBUMARTIST, 'music/x.flac',
        {'albumartist': 'Band', 'album': 'Album', 'track': '3', 'title': 'Song', 'artist': 'Guest'},
        'music/03 - Song - Guest.flac',
        id='I664-no-disc'),
    pytest.param(  # the answer's pattern, on an album with two discs
        DISC_FOLDERS, 'music/x.flac', dict(ALBUM, disctotal='2'),
        '/mnt/data/music/Band/Album/Disc 1/03 - Song.flac',
        id='D1028-two-discs'),
    pytest.param(  # another layout posted there
        '/home/carbonjamster/Music/%albumartist%/%album%/$num(%discnumber%,2)-$num(%track%,2) - %title%',
        'music/x.flac', ALBUM, '/home/carbonjamster/Music/Band/Album/01-03 - Song.flac',
        id='D1028-disc-prefix'),
    pytest.param(  # the first of the Pattern Combo's default patterns (mainwin/patterncombo.py)
        '%artist% - $num(%track%,2) - %title%', 'music/x.mp3',
        {'artist': 'Artist', 'track': '1', 'title': 'Title'}, 'music/Artist - 01 - Title.mp3',
        id='default-pattern'),
    pytest.param(  # a saved pattern in github.com/xeruf/dotfiles .config/puddletag/puddletag.conf
        '$meta_sep(artist," & ") - %title%', 'music/x.flac',
        {'artist': ['A', 'B'], 'title': 'Title'}, 'music/A & B - Title.flac',
        id='xeruf-dotfiles'),
])
def test_shared_tag_to_file(tag_to_file, pattern, path, tags, expected):
    assert tag_to_file(pattern, path, **tags) == expected


def test_dot_folder_is_no_folder(tag_to_file):
    # D1028's answer: "Using a dot as "no-op" between them seems to work."
    new_path = tag_to_file(DISC_FOLDERS, 'music/x.flac', **dict(ALBUM, disctotal='1'))
    assert os.path.normpath(new_path) == '/mnt/data/music/Band/Album/03 - Song.flac'


def test_empty_folder_is_no_folder(tag_to_file):
    # D1028 asks for no disc folder on single-disc albums; its answer:
    # "Multiple path-separators next to each other causes some funny behavior",
    # a folder named "".
    pattern = DISC_FOLDERS.replace(',.)', ',)')
    assert tag_to_file(pattern, 'music/x.flac', **dict(ALBUM, disctotal='1')) == '/mnt/data/music/Band/Album/03 - Song.flac'


RELATIVE_DISC_FOLDERS = '%album%/$if(%discnumber%,Disc %discnumber%,)/%title%'


@pytest.mark.parametrize('pattern, path, tags, expected', [
    (RELATIVE_DISC_FOLDERS, 'library/Album/x.flac', {'album': 'Album', 'title': 'Song'},
     'library/Album/Song.flac'),
    (RELATIVE_DISC_FOLDERS, 'library/Album/Disc 1/x.flac',
     {'album': 'Album', 'title': 'Song', 'discnumber': '1'}, 'library/Album/Disc 1/Song.flac'),
    ('%genre%/%album%/%title%', 'library/Album/x.flac', {'album': 'Album', 'title': 'Song'},
     'library/Album/Song.flac'),
])
def test_relative_pattern_counts_only_folders_it_makes(tag_to_file, pattern, path, tags, expected):
    # A file already laid out by the pattern stays in its folder, also when
    # a folder comes out empty: function.txt, "a directory that comes out
    # empty doesn't count". Synthetic layouts, the first one D1028's.
    assert tag_to_file(pattern, path, **tags) == expected
