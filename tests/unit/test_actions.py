"""Actions: the functions of the Functions dialog, run through findfunc.Function,
and the .action files that save chains of them.

Expected results come from docsrc/source/function.txt unless noted.
"""
import json
import os

import pytest

from puddlestuff import audioinfo
from puddlestuff.constants import ACTIONDIR, DATADIR
from puddlestuff.findfunc import (Function, Macro, apply_actions, apply_macros, load_macro_info,
                                  parse_field_list, save_macro)
from puddlestuff.puddleobjects import load_actions


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


@pytest.mark.xfail(strict=True, raises=AttributeError,
                   reason='Macro.apply_action passes its functions to apply_macros, which expects actions')
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
                 id='all-then-all-but',
                 marks=pytest.mark.xfail(strict=True, reason='__all before ~ adds back the fields after it')),
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


@pytest.mark.parametrize('name, args, before, after', [
    # Merge Field: "Rock, Rap and Reggae ... the single value Rock;Rap;Reggae"
    ('merge_values', [';'], ['Rock', 'Rap', 'Reggae'], ['Rock;Rap;Reggae']),
    # Remove duplicate values: "Rap, Rock and rap ... (without
    # case-sensitivity) will leave Rap and Rock"
    ('remove_dupes', [False], ['Rap', 'Rock', 'rap'], ['Rap', 'Rock']),
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
    pytest.param(' artist; title ', marks=pytest.mark.xfail(
        strict=True, reason="the spaces aren't trimmed, so artist and title are removed too")),
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
