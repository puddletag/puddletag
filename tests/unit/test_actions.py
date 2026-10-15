"""Actions: the functions of the Functions dialog, run through findfunc.Function,
and the .action files that save chains of them.

Expected results come from docsrc/source/function.txt unless noted.
"""
import json
import os
import shutil
import tempfile

import mutagen.id3
import pytest

from puddlestuff import audioinfo
from puddlestuff.constants import ACTIONDIR, DATADIR
from puddlestuff.findfunc import (Function, Macro, apply_actions, apply_macros, load_macro_info,
                                  parse_field_list, save_macro)
from puddlestuff.puddleobjects import load_actions
from puddlestuff.util import write
from test_covers import NO_FIELDS


def make_action(name, fields, *args):
    action = Function(name)
    action.setTag(list(fields))
    action.setArgs(list(args))
    return action


def as_macro(*funcs):
    """An action as the Actions window holds it."""
    macro = Macro()
    macro.actions = list(funcs)
    return macro


def values(changes):
    """An action's changes, each value as a list, as the table shows it."""
    return {field: value if isinstance(value, list) else [value] for field, value in changes.items()}


def save(tag, changes):
    """Writes an action's changes the way the table's write ends (Tag.update,
    then Tag.save) and reads the file back."""
    tag.update(changes)
    tag.save()
    return audioinfo.Tag(tag['__path'])


def test_convert_to_ascii():
    # The docs' example. The action runs on each value of the field.
    action = make_action('to_ascii', ['title'])
    assert action.funcname == 'Convert to ASCII'
    assert action.runFunction(text=['abc äéç цы'], m_tags={'title': ['abc äéç цы']}) == ['abc aec tsy']


# The default actions shipped in puddlestuff/data, by name.
SHIPPED = {'Case Conversion': 'caseconversion.action', 'Standard': 'standard.action'}


def describe(func):
    """A loaded function as its .action file section writes it."""
    return {'func_name': func.function.__name__, 'module': func.function.__module__,
            'fields': func.tag, 'arguments': [str(arg) for arg in func.args]}


@pytest.mark.parametrize('name', sorted(SHIPPED))
def test_default_action_loads_as_written(name):
    # Expected: the shipped file's own content.
    path = os.path.join(DATADIR, SHIPPED[name])
    with open(path) as f:
        saved = json.load(f)
    funcs, loaded_name = load_macro_info(path)
    assert loaded_name == name
    assert [describe(func) for func in funcs] == [saved[f'Func{i}'] for i in range(len(saved) - 1)]


def test_default_case_conversion_action():
    # docsrc/source/tut2.txt: the Case Conversion action's function changes
    # the album, title and artist fields to "Mixed Case", which capitalises
    # each word and lowers the rest (function.txt). Synthetic title.
    funcs, name = load_macro_info(os.path.join(DATADIR, SHIPPED['Case Conversion']))
    assert set(funcs[0].tag) == {'album', 'title', 'artist'}
    assert funcs[0].runFunction(text=['the BEST of'], m_tags={'title': ['the BEST of']}) == ['The Best Of']


def test_saved_action_loads_back(tmp_path):
    # Synthetic action. Replace's last two arguments are checkboxes.
    funcs = [make_action('titleCase', ['artist', 'title'], 'UPPER CASE', '., !'),
             make_action('replace', ['__all'], '_', ' ', True, False)]
    path = str(tmp_path / 'tidy.action')
    save_macro(path, 'Tidy', funcs)
    loaded, name = load_macro_info(path)
    assert name == 'Tidy'
    assert [(f.function, f.tag, f.args) for f in loaded] == [(f.function, f.tag, f.args) for f in funcs]


def test_clean_profile_gets_the_default_actions(clean_profile):
    # The action shortcuts call load_actions() at startup, before the
    # Actions window has copied the defaults into a new profile.
    for _ in range(2):  # the copies stay: the second call finds them
        actions = load_actions()
        assert sorted(name for funcs, name, path in actions) == sorted(SHIPPED)
        for funcs, name, path in actions:
            assert os.path.dirname(path) == ACTIONDIR
            shipped = load_macro_info(os.path.join(DATADIR, SHIPPED[name]))[0]
            assert [describe(f) for f in funcs] == [describe(f) for f in shipped]


# Running actions -------------------------------------------------------------

def test_each_step_sees_what_the_steps_before_set(make_audio, tmp_path):
    # #13: an action of "Format COMPILATION using 0", "Format ALBUMARTIST
    # using %artist%" and a file name from %albumartist% gave
    # "%albumartist% - Grasshopper - 01 - City Girls.flac", and set neither
    # COMPILATION=0 nor ALBUMARTIST=J.J. Cale. The report's tags; the last
    # step is Tag to filename, which adds the extension the report shows.
    path = make_audio('track.flac', tmp_path, artist='J.J. Cale', album='Grasshopper',
                      tracknumber='01', title='City Girls')
    action = [make_action('format', ['compilation'], '0'),
              make_action('format', ['albumartist'], '%artist%'),
              make_action('move', ['__path'], '%albumartist% - %album% - %track% - %title%')]
    assert values(apply_actions(action, audioinfo.Tag(str(path)))) == {
        'compilation': ['0'], 'albumartist': ['J.J. Cale'],
        '__path': [str(tmp_path / 'J.J. Cale - Grasshopper - 01 - City Girls.flac')]}


def test_steps_on_one_field_run_in_order():
    # Synthetic action, after the "Fix spaces" action shared in
    # jprieton/puddletag-actions: underscores to spaces in every field, runs
    # of spaces to one, then trimmed. Synthetic tags.
    action = [make_action('replace', ['__all'], '_', ' ', False, False),
              make_action('regex', ['title'], r'\s+', ' ', False),
              make_action('strip', ['title'])]
    audio = {'title': ['  Hello__World_ '], 'artist': ['Some_Band']}
    assert values(apply_actions(action, audio)) == {'title': ['Hello World'], 'artist': ['Some Band']}


def test_saved_function_settings_as_an_action():
    # One user's saved Functions settings (github.com/victorcdp/dotfiles,
    # puddletag/.config/puddletag/function_settings) run as one action:
    # Replace \\ with ; in artist (Match Case), then Split fields using
    # separator ; on __all. Synthetic tags.
    action = [make_action('replace', ['artist'], '\\\\', ';', True, False),
              make_action('split_by_sep', ['__all'], ';')]
    changes = values(apply_actions(action, {'artist': ['Artist One\\\\Artist Two'], 'title': ['Song']}))
    assert changes['artist'] == ['Artist One', 'Artist Two']
    assert changes.get('title', ['Song']) == ['Song']


def test_quick_action_uses_the_selected_fields():
    # menus.txt: an action that converts artist, album and title to Mixed
    # Case, run as a Quick Action on the selected originalartist and band
    # fields, "will be applied to each field respectively". Synthetic tags.
    action = as_macro(make_action('titleCase', ['artist', 'album', 'title'], 'Mixed Case', '., !'))
    audio = {'artist': ['the artist'], 'originalartist': ['the original'], 'band': ['the band']}
    assert values(apply_macros([action], audio, {}, ['originalartist', 'band'])) == {
        'originalartist': ['The Original'], 'band': ['The Band']}


def test_action_changes_only_the_fields_it_names(make_audio, tmp_path):
    # #1038: "Replace artist, album, title: '.'->'', Match Case: Yes", run as
    # a Quick Action with every cell selected, also took the dot out of the
    # file name. That is what a Quick Action does (menus.txt); as an Action
    # it changes only the fields it names. Synthetic tags.
    path = make_audio('musicfile.mp3', tmp_path, artist='A.B.', album='C.D.', title='E.F.', genre='G.H.')
    tag = audioinfo.Tag(str(path))
    action = as_macro(make_action('replace', ['artist', 'album', 'title'], '.', '', True, False))
    assert values(apply_macros([action], tag, {})) == {'artist': ['AB'], 'album': ['CD'], 'title': ['EF']}
    assert values(apply_macros([action], tag, {}, ['genre', '__filename'])) == {
        'genre': ['GH'], '__filename': ['musicfilemp3']}


def test_checked_actions_run_one_after_another(tmp_path):
    # tut2.txt: "Actions are just a bunch of functions run one after the
    # other"; the Actions window runs the checked actions in their listed
    # order. Synthetic actions: run the other way round, the title would be
    # "Hello world".
    first, second = str(tmp_path / 'first.action'), str(tmp_path / 'second.action')
    save_macro(first, 'Underscores', [make_action('replace', ['title'], '_', ' ', False, False)])
    save_macro(second, 'Case', [make_action('titleCase', ['title'], 'Mixed Case', '., !')])
    assert values(apply_macros([Macro(first), Macro(second)], {'title': ['hello_world']}, {})) == {
        'title': ['Hello World']}


def test_one_action_applied_by_itself():
    # Synthetic action and title.
    macro = as_macro(make_action('titleCase', ['title'], 'UPPER CASE', ''))
    assert values(macro.apply_action({'title': ['hello']})) == {'title': ['HELLO']}


# tut3.txt, "Functions": the fields a field list writes to, for a file with
# these fields (synthetic).
FIELD_LIST_TAGS = {'artist': ['a'], 'title': ['t'], 'year': ['y'], 'genre': ['g'],
                   'musicip_puid': ['p'], 'fingerprint': ['f'],
                   '__filename': 'x.mp3', '__dirname': 'd', '__path': '/d/x.mp3'}


@pytest.mark.parametrize('fields, selected, expected', [
    # "__all will write to all the fields found in a file except filename
    # related fields like __dirname, __filename"
    pytest.param(['__all'], [], {'artist', 'title', 'year', 'genre', 'musicip_puid', 'fingerprint'},
                 id='all'),
    # "You can enter your own fields like albumartist"; "albumartist, __selected"
    pytest.param(['albumartist', '__selected'], ['genre'], {'albumartist', 'genre'}, id='own-and-selected'),
    # "~artist, title, year will write to all but the artist, title and year fields"
    pytest.param(['~artist', 'title', 'year'], [], {'genre', 'musicip_puid', 'fingerprint'}, id='all-but'),
    # "~__selected will write to all, but the selected"
    pytest.param(['~__selected'], ['genre', 'year'], {'artist', 'title', 'musicip_puid', 'fingerprint'},
                 id='all-but-selected'),
    # "__all, ~musicip_puid, fingerprint does as suggested": Case Conversion
    # to all but musicip_puid and fingerprint, "that should remain unchanged"
    pytest.param(['__all', '~musicip_puid', 'fingerprint'], [], {'artist', 'title', 'year', 'genre'},
                 id='all-then-all-but'),
])
def test_field_list(fields, selected, expected):
    assert set(parse_field_list(fields, FIELD_LIST_TAGS, selected)) == expected


# The examples of function.txt, run as actions.
GUY = {'artist': ['A Guy'], 'album': ['Screeching'], 'title': ['Excessively Emo'], 'track': ['2']}


@pytest.mark.parametrize('pattern, expected', [
    ('I wanna write my own.', ['I wanna write my own.']),
    ('%genre%', []),  # "would return nothing, because there ain't no genre field"
    ("I don't like an %title% %artist%...%album%", ["I don't like an Excessively Emo A Guy...Screeching"]),
    ("I don't like an $lower(%title% $mid(%artist%,2,10)) $lower(%album%).",
     ["I don't like an excessively emo guy screeching."]),
])
def test_format_value(pattern, expected):
    assert values(apply_actions([make_action('format', ['comment'], pattern)], GUY)).get('comment', []) == expected


@pytest.mark.parametrize('characters, text, expected', [
    # Case Conversion: Mixed Case with "." and a space, then "." alone
    ('. ', 'this is my name. and my surname. with a dot.here and there.',
     'This Is My Name. And My Surname. With A Dot.Here And There.'),
    ('.', 'this is my name. and my surname. with a dot.here and there.',
     'This is my name. and my surname. with a dot.Here and there.'),
    # The default characters, then with "(" added: #323 ("Fails to convert
    # "(word" to "(Word""), whose reporter found the list. Synthetic title.
    ('., !', 'live (acoustic version)', 'Live (acoustic Version)'),
    ('., !(', 'live (acoustic version)', 'Live (Acoustic Version)'),
])
def test_mixed_case(characters, text, expected):
    action = [make_action('titleCase', ['title'], 'Mixed Case', characters)]
    assert values(apply_actions(action, {'title': [text]})) == {'title': [expected]}


@pytest.mark.parametrize('name, args, before, after', [
    # Merge Field: "Rock, Rap and Reggae ... the single value Rock;Rap;Reggae"
    ('merge_values', [';'], ['Rock', 'Rap', 'Reggae'], ['Rock;Rap;Reggae']),
    # Remove duplicate values: "Rap, Rock and rap ... (without
    # case-sensitivity) will leave Rap and Rock"
    ('remove_dupes', [False], ['Rap', 'Rock', 'rap'], ['Rap', 'Rock']),
    # Sort values: "Sorts the values in a multiple-valued field using
    # either Ascending or Descending order". Match Case is on: off, the
    # order follows the system locale's collation. Synthetic values.
    ('sort', ['Ascending', True], ['Jazz', 'Rock', 'Blues'], ['Blues', 'Jazz', 'Rock']),
    ('sort', ['Descending', True], ['Jazz', 'Rock', 'Blues'], ['Rock', 'Jazz', 'Blues']),
    # Split fields using separator, both examples
    ('split_by_sep', [';'], ['Rap;Rock;Dubstep'], ['Rap', 'Rock', 'Dubstep']),
    ('split_by_sep', [';'], ['Rock;Rap', 'Classical;Guitar Solo'], ['Rock', 'Rap', 'Classical', 'Guitar Solo']),
    # Trim Whitespace
    ('strip', [], [" there's a space before and one after "], ["there's a space before and one after"]),
])
def test_function_on_a_field(name, args, before, after):
    assert values(apply_actions([make_action(name, ['genre'], *args)], {'genre': before})) == {'genre': after}


@pytest.mark.parametrize('tags, text, pattern, output, expected', [
    ({}, 'First Second', '%1 %2', '%2 %1', 'Second First'),
    ({'artist': ['Eminem/Recovery']}, '%artist%', '%1/%2', '%2', 'Recovery'),
    ({'artist': ['Eminem/Recovery']}, '%artist%', '%1/%2', '%1', 'Eminem'),
    ({}, 'Jimmy-01/Rebellious Angel', '%1-%2/%3', '$num(%2, 1)', '1'),
])
def test_text_to_tag(tags, text, pattern, output, expected):
    action = [make_action('texttotag', ['comment'], text, pattern, output)]
    assert values(apply_actions(action, tags)) == {'comment': [expected]}


def test_remove_fields(make_audio, tmp_path):
    # Synthetic tags.
    path = make_audio('song.flac', tmp_path, artist='Artist', genre='Genre', comment='Comment')
    tag = audioinfo.Tag(str(path))
    saved = save(tag, apply_actions([make_action('remove_fields', ['genre', 'comment'])], tag))
    assert audioinfo.usertags(saved) == {'artist': ['Artist']}


@pytest.mark.parametrize('keep', [
    'artist;title',
    ' artist; title ',
])
def test_remove_all_fields_except(make_audio, tmp_path, keep):
    # "artist;title and  artist; title  are equivalent". Synthetic tags.
    path = make_audio('song.flac', tmp_path, artist='Artist', title='Title', album='Album', genre='Genre')
    tag = audioinfo.Tag(str(path))
    saved = save(tag, apply_actions([make_action('remove_except', ['__all'], keep)], tag))
    assert audioinfo.usertags(saved) == {'artist': ['Artist'], 'title': ['Title']}


@pytest.mark.parametrize('start, restart, padding, expected', [
    # "Numbers tracks sequentially beginning with Start"
    (1, False, 1, ['1', '2', '3']),
    # "Restart Numbering at each directory will restart the numbering from
    # Start for each directory encountered"
    (1, True, 1, ['1', '2', '1']),
    # "if a file has track number '12', having a padding of 3 will return the
    # number '012', while a padding of 1 will leave the number unchanged"
    (12, False, 3, ['012', '013', '014']),
    (12, False, 1, ['12', '13', '14']),
])
def test_autonumbering(make_audio, tmp_path, start, restart, padding, expected):
    # Three synthetic files, two in one folder, run as one Action: the files
    # share one state, as in mainwin/funcs.py applyaction.
    files = [audioinfo.Tag(str(make_audio(name, tmp_path / folder)))
             for folder, name in (('one', 'a.mp3'), ('one', 'b.mp3'), ('two', 'c.mp3'))]
    action = [make_action('autonumbering', ['track'], start, restart, padding)]
    state = {'__total_files': str(len(files)), '__files': files}
    assert [values(apply_actions(action, f, state))['track'] for f in files] == [[n] for n in expected]


# The encodings the Functions dialog offers for Convert from non-standard
# encoding, each with a synthetic text in a script it holds. cp1258 holds
# Vietnamese tones as combining marks.
ENCODED = {
    'big5': '藏經', 'big5hkscs': '藏經', 'cp1250': 'Příliš žluťoučký kůň', 'cp1251': 'Группа крови',
    'cp1252': '“Café” – €5', 'cp1253': 'Καλημέρα', 'cp1254': 'Gönül Dağı', 'cp1255': 'שלום', 'cp1256': 'مرحبا',
    'cp1257': 'Žalgiris ąčęėįšųū', 'cp1258': 'Việt Nam', 'cp932': '日本語', 'euc_jis_2004': '日本語',
    'euc_jp': '日本語', 'gb18030': '中文', 'gb2312': '中文', 'gbk': '中文', 'hz': '中文', 'johab': '한국어',
    'shift_jis': '日本語',
}


def latin1_title(text, encoding):
    """An ID3 title of Latin-1 text holding text written in encoding, as a
    program writing the system's code page leaves it."""
    return mutagen.id3.TIT2(encoding=mutagen.id3.Encoding.LATIN1, text=[text.encode(encoding).decode('latin-1')])


def converted(path, encoding):
    tag = audioinfo.Tag(str(path))
    return save(tag, apply_actions([make_action('enconvert', ['title'], encoding)], tag))['title']


@pytest.mark.parametrize('encoding', sorted(ENCODED))
def test_convert_from_non_standard_encoding(make_audio, tmp_path, encoding):
    # "If your files were written using non-standard encoding (eg cp1251 on
    # Windows) you can use this Function to fix 'em." ID3v2 allows Latin-1
    # text, which puddletag shows byte for byte.
    path = make_audio('song.mp3', tmp_path)
    id3 = mutagen.id3.ID3(str(path))
    id3.add(latin1_title(ENCODED[encoding], encoding))
    id3.save()
    assert converted(path, encoding) == [ENCODED[encoding]]


def test_convert_an_id3v1_tag(make_audio, tmp_path):
    # ID3v1 holds Latin-1 text only, the case of the docs' example.
    path = make_audio('song.mp3', tmp_path)
    id3 = mutagen.id3.ID3()
    id3.add(latin1_title(ENCODED['cp1251'], 'cp1251'))
    id3.save(str(path), v1=2)
    mutagen.id3.delete(str(path), delete_v1=False)
    assert converted(path, 'cp1251') == [ENCODED['cp1251']]


def test_convert_keeps_correct_text(make_audio, tmp_path):
    # Run on a selection where only some files hold mis-read text, it fixes
    # those and keeps the others: a value with a character beyond Latin-1
    # wasn't read as Latin-1. The docs don't cover text already right
    # (synthetic titles).
    broken = make_audio('broken.mp3', tmp_path)
    id3 = mutagen.id3.ID3(str(broken))
    id3.add(latin1_title(ENCODED['cp1251'], 'cp1251'))
    id3.save()
    correct = make_audio('correct.mp3', tmp_path, title=ENCODED['cp1251'])
    assert [converted(path, 'cp1251') for path in (broken, correct)] == [[ENCODED['cp1251']]] * 2


@pytest.mark.parametrize('pattern, source', [
    ('lyrics.txt', 'Music/artist/album/lyrics.txt'),
    ('../lyrics.txt', 'Music/artist/lyrics.txt'),
    ('%album%', 'Music/artist/album/END'),
    ('{root}/textfiles/lyrics.txt', 'textfiles/lyrics.txt'),
])
def test_import_text_file(make_audio, tmp_path, pattern, source):
    # The four examples, "For the file with path
    # /mnt/Music/artist/album/filename.mp3 and with the tag, artist=Black
    # Eyed Peas, album=END" (here under tmp_path, /mnt/textfiles too): "the
    # files complete text is loaded into that field". Synthetic texts, a
    # different one in each place.
    path = make_audio('filename.mp3', tmp_path / 'Music/artist/album', artist='Black Eyed Peas', album='END')
    texts = {}
    for name in ['Music/artist/album/END', 'Music/artist/album/lyrics.txt', 'Music/artist/lyrics.txt',
                 'textfiles/lyrics.txt']:
        texts[name] = f'Lyrics from {name}\n\nLast line\n'
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_text(texts[name])
    tag = audioinfo.Tag(str(path))
    action = [make_action('import_text', ['unsyncedlyrics'], pattern.format(root=tmp_path))]
    # id3.txt: lyrics read as Language|Description|Lyrics, and "If only text
    # is entered ... the language und (undetermined) will be used".
    assert save(tag, apply_actions(action, tag))['unsyncedlyrics'] == ['und||' + texts[source]]


def write_as_table(tag, changes):
    """Writes changes as the table does (TagModel.setRowData), which renames
    the file's folder for a new __dirpath. Returns the file's new path."""
    tag.library, tag.preview = None, {}  # set by the table on each file it loads
    write(tag, changes)
    return tag.filepath


def tag_to_dir(path, pattern):
    tag = audioinfo.Tag(str(path))
    return write_as_table(tag, apply_actions([make_action('tag_dir', NO_FIELDS, pattern)], tag))


# Tag to filename's example file, whose folder Tag to Dir renames.
UNSORTED = 'home/concentricpuddle/multimedia/music/Indie/unsorted'
INDIE = 'home/concentricpuddle/multimedia/music/Indie'
UNKNOWN = {'artist': 'Relatively Unknown', 'title': 'Horrible for everyone else', 'album': 'Fans like it'}
DISC_FOLDER = '{root}/mnt/music/%album%/$if(%discnumber%,Disc %discnumber%,)'


@pytest.mark.parametrize('pattern, tags, expected', [
    # tut2.txt, Rename Dir: "if the Pattern Combo contained, %artist% -
    # %album%, it would behave the same way as file renaming (except on the
    # directory)". It's the dialog's default pattern too.
    ('%artist% - %album%', UNKNOWN, INDIE + '/Relatively Unknown - Fans like it'),
    # The rules of Tag to filename: "For every slash, the file is moved up
    # one directory";
    ('%artist%/%album%', UNKNOWN, 'home/concentricpuddle/multimedia/music/Relatively Unknown/Fans like it'),
    # "an absolute path, by starting the pattern with a slash", and
    # "Intermediate directories will be created if they don't exist";
    ('{root}/mnt/library/%album%', UNKNOWN, 'mnt/library/Fans like it'),
    # "if the artist is AC/DC, it will not create an AC directory";
    ('%artist%', dict(UNKNOWN, artist='AC/DC'), INDIE + '/ACDC'),
    # the characters it removes (synthetic artist);
    ('%artist%', dict(UNKNOWN, artist='a\\b*c?d"e|f:g/h;i'), INDIE + '/abcdefgh;i'),
    # "a directory that comes out empty doesn't count" (synthetic pattern);
    ('%artist%/$if(%year%,%year%,)/%album%', UNKNOWN,
     'home/concentricpuddle/multimedia/music/Relatively Unknown/Fans like it'),
    # and "only adds a Disc directory when the file has a disc number",
    (DISC_FOLDER, dict(UNKNOWN, discnumber='1'), 'mnt/music/Fans like it/Disc 1'),
    (DISC_FOLDER, UNKNOWN, 'mnt/music/Fans like it'),
    # also as a relative pattern, where the Disc directory left out doesn't
    # count.
    ('%album%/$if(%discnumber%,Disc %discnumber%,)', dict(UNKNOWN, discnumber='1'),
     'home/concentricpuddle/multimedia/music/Fans like it/Disc 1'),
    ('%album%/$if(%discnumber%,Disc %discnumber%,)', UNKNOWN, INDIE + '/Fans like it'),
])
def test_tag_to_dir(make_audio, tmp_path, pattern, tags, expected):
    # "Works as Tag To Filename (below), but renames/moves directories
    # instead."
    path = make_audio('unknown.mp3', tmp_path / UNSORTED, **tags)
    new_path = tag_to_dir(path, pattern.format(root=tmp_path))
    assert (new_path, path.parent.exists()) == (str(tmp_path / expected / 'unknown.mp3'), False)
    assert audioinfo.Tag(new_path)['title'] == [UNKNOWN['title']]


@pytest.fixture
def other_filesystem(tmp_path):
    """A folder on another filesystem than tmp_path's: /dev/shm is a tmpfs
    of its own on Linux."""
    if not os.path.isdir('/dev/shm') or os.stat('/dev/shm').st_dev == os.stat(tmp_path).st_dev:
        pytest.skip("/dev/shm isn't another filesystem")
    folder = tempfile.mkdtemp(dir='/dev/shm')
    yield folder
    shutil.rmtree(folder)


def test_tag_to_dir_on_another_filesystem(make_audio, tmp_path, other_filesystem):
    # "Directories will only be moved if the destination dir resides on the
    # same filesystem as the source." The table shows the error.
    path = make_audio('unknown.mp3', tmp_path / UNSORTED, **UNKNOWN)
    with pytest.raises(OSError):
        tag_to_dir(path, other_filesystem + '/%album%')
    assert (path.exists(), os.listdir(other_filesystem)) == (True, [])
