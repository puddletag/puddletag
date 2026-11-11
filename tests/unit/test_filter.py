"""Filter expressions (puddlestuff/audio_filter.py), run on real files the way
the Filter panel runs them (tagmodel.py applyFilter).

Expected results come from docsrc/source/filter.txt unless noted. Tags are
synthetic, the docs' own example values where they give them. On a fresh
profile, the fields the filter knows are audioinfo's default field list.
"""
import pytest

from puddlestuff import audioinfo
from puddlestuff.audio_filter import parse
from test_covers import FRONT, write

# The docs' example artist and title.
BONGO = {'artist': 'Bongo Maffin', 'title': 'Monster', 'tracknumber': '05', 'genre': 'Kwaito'}


@pytest.fixture
def matches(make_audio, tmp_path):
    """Whether a new file with these tags passes the filter expression.

    A plain word is searched for in every field, the file's path included,
    so the words tested here don't occur in tmp_path.
    """
    def run(expression, **tags):
        audio = audioinfo.Tag(str(make_audio('song.flac', tmp_path / 'music', **tags)))
        return parse(audio, expression)
    return run


@pytest.mark.parametrize('expression, tags, expected', [
    # "string: ... True if a contains string in any of it's fields"
    pytest.param('Maffin', BONGO, True, id='word'),
    pytest.param('Nowhere', BONGO, False, id='word-absent'),
    pytest.param('"Bongo Maffin"', BONGO, True, id='quoted-words'),
    pytest.param('MISSING artist', BONGO, False, id='missing'),
    pytest.param('MISSING style', BONGO, True, id='missing-absent'),
    pytest.param('PRESENT artist', BONGO, True, id='present'),
    pytest.param('PRESENT style', BONGO, False, id='present-absent'),
    # GREATER/LESS: "If both are numbers, they're compared as numbers": as
    # text, "9" isn't less than "10".
    pytest.param('track LESS 10', dict(BONGO, tracknumber='9'), True, id='less-numbers'),
    pytest.param('track GREATER 10', dict(BONGO, tracknumber='9'), False, id='greater-numbers'),
    pytest.param('artist LESS "some words"', BONGO, True, id='less-text'),
    pytest.param('artist GREATER "some words"', BONGO, False, id='greater-text'),
    # "...by character code, so capital letters come before lower case ones"
    pytest.param('artist GREATER "a"', BONGO, False, id='greater-text-case'),
    # EQUAL: "Numbers are compared as text too, so track EQUAL 5 is False
    # for a track stored as 05"
    pytest.param('track EQUAL 5', BONGO, False, id='equal-numbers'),
    pytest.param('track EQUAL 05', BONGO, True, id='equal-numbers-text'),
    pytest.param('artist EQUAL "bongo maffin"', BONGO, True, id='equal-text'),
    pytest.param('artist HAS Maffin', BONGO, True, id='has'),
    pytest.param('%title% HAS "Remixed By"', dict(BONGO, title='Monster (Remixed By DJ)'), True, id='has-quoted'),
    pytest.param('artist IS "Bongo Maffin"', BONGO, True, id='is-quoted'),
    pytest.param('title IS Monster', BONGO, True, id='is'),
    pytest.param('title IS monster', BONGO, True, id='is-case'),
    pytest.param('artist IS Bongo', BONGO, False, id='is-part'),
    pytest.param('title MATCHES "^mon"', BONGO, True, id='matches'),
    pytest.param('%title% MATCHES "\\(live\\)$"', dict(BONGO, title='Monster (Live)'), True, id='matches-escaped'),
    pytest.param('%title% MATCHES "\\(live\\)$"', dict(BONGO, title='Live (Monster)'), False, id='matches-not'),
    pytest.param('artist IS "Bongo Maffin" AND title IS Monster', BONGO, True, id='and'),
    pytest.param('artist IS "Bongo Maffin" AND title IS Other', BONGO, False, id='and-one'),
    pytest.param('artist IS "Bongo Maffin" OR title IS Other', BONGO, True, id='or'),
    pytest.param('artist IS Nobody OR title IS Other', BONGO, False, id='or-none'),
    pytest.param('NOT artist IS "Bongo Maffin"', BONGO, False, id='not'),
    pytest.param('NOT title IS Other', BONGO, True, id='not-false'),
    pytest.param('NOT Maffin', BONGO, False, id='not-word'),
    pytest.param('NOT Nowhere', BONGO, True, id='not-word-absent'),
    # "If the field isn't present in the file it'll evaluate to an empty string"
    pytest.param('composer IS ""', BONGO, True, id='field-absent'),
    # A word that's no field "will be interpreted as normal text"
    pytest.param('madeupfield IS madeupfield', BONGO, True, id='not-a-field'),
])
def test_documented_filters(matches, expression, tags, expected):
    assert matches(expression, **tags) is expected



@pytest.mark.parametrize('expression, tags, expected', [
    # #638: filters that "filter nothing"; synthetic values.
    pytest.param('%title% IS "at"', {'title': 'At'}, True, id='I638-is'),
    pytest.param('%genre% HAS "DnB"', {'genre': 'Drum & Bass / DnB'}, True, id='I638-has'),
    pytest.param('genre HAS "DnB"', {'genre': 'Drum & Bass / DnB'}, True, id='I638-has-field'),
    # #665, #929: filtering by a single "-" crashed; it's a plain search.
    pytest.param('-', {'title': 'A - B'}, True, id='I929-dash'),
    # #1026: an empty list for albumartist filters, on files whose
    # albumartist is "Various Artists". albumartist isn't in the default
    # field list; filter.txt: a word is a field also when "the field is
    # present in the file".
    pytest.param('albumartist has "Various"', {'albumartist': 'Various Artists'}, True, id='I1026-has'),
    pytest.param('albumartist IS "Various Artists"', {'albumartist': 'Various Artists'}, True, id='I1026-is'),
    pytest.param('albumartist IS "Various"', {'albumartist': 'Various Artists'}, False, id='I1026-is-part'),
    # #463: "Filtering a field with non-English char" finds nothing; it
    # gives no example, so a synthetic one.
    pytest.param('artist IS "björk"', {'artist': 'Björk'}, True, id='I463-is'),
    pytest.param('artist HAS Λόγος', {'artist': 'Λόγος'}, True, id='I463-has-word'),
    pytest.param('artist IS björk', {'artist': 'Björk'}, True, id='I463-is-word'),
    pytest.param('björk', {'artist': 'Bjarne'}, False, id='I463-word-prefix'),
])
def test_reported_filters(matches, expression, tags, expected):
    assert matches(expression, **tags) is expected


def test_invalid_regex_does_not_crash(matches):
    # #665, #929: a filter the user is still typing must not crash
    # puddletag; it matches nothing. Synthetic expression, missing a "(".
    assert matches('title MATCHES "live)$"', title='Song (Live)') is False


def test_word_search_skips_the_cover(make_audio, tmp_path):
    # "string: Evaluates to True if a contains string in any of it's
    # fields." A cover isn't text, so the word search passes over it.
    path = make_audio('song.flac', tmp_path / 'music', **BONGO)
    write(path, [FRONT])
    audio = audioinfo.Tag(str(path))
    assert parse(audio, 'Maffin') is True
    assert parse(audio, 'Nowhere') is False


@pytest.mark.parametrize('expression', [
    pytest.param('(artist IS "Bongo Maffin") IS (title IS Monster)', id='is'),
    pytest.param('(artist IS "Bongo Maffin") EQUAL (title IS Monster)', id='equal'),
    pytest.param('artist IS (title IS Monster)', id='is-right'),
    pytest.param('(artist IS "Bongo Maffin") HAS (title IS Monster)', id='has'),
    pytest.param('(artist IS "Bongo Maffin") MATCHES Monster', id='matches'),
    pytest.param('(artist IS "Bongo Maffin") GREATER (title IS Monster)', id='greater'),
])
def test_nested_comparison(matches, expression):
    # filter.txt: "field IS expr", "field HAS expr" and "field MATCHES
    # expr" take a field on the left; "If it evaluates to True for a file,
    # then that file will be shown." Beyond it, an expression that can't be
    # evaluated shows no file, with no message, as a broken regex does.
    assert matches(expression, **BONGO) is False


def test_not_of_a_comparison(matches):
    # filter.txt: "NOT expr: Evaluates to True if expr is False."
    assert matches('NOT (artist IS "Bongo Maffin")', **BONGO) is False


def test_script_error_in_a_filter(matches):
    # An expression that can't be evaluated (a quoted script missing its
    # ")", synthetic) shows no file, with no message.
    assert matches('title IS "$upper(Monster"', **BONGO) is False


@pytest.mark.parametrize('expression, expected', [
    # "Any text in the form %string% (if it's not enclosed in quotes) will
    # be assumed to be a field." and "Evaluates to True if field is not
    # present in a file."
    pytest.param('MISSING %artist%', False, marks=pytest.mark.xfail(
        strict=True, reason='MISSING and PRESENT read %field% as text'), id='missing-percent'),
    pytest.param('PRESENT %artist%', True, marks=pytest.mark.xfail(
        strict=True, reason='MISSING and PRESENT read %field% as text'), id='present-percent'),
    pytest.param('MISSING %style%', True, id='missing-percent-absent'),
    # "Comparisons ignore case"; the docs are silent for field names.
    pytest.param('MISSING Artist', False, id='missing-case'),
    pytest.param('PRESENT ARTIST', True, id='present-case'),
    # A quoted field name is read as the field too (synthetic).
    pytest.param('MISSING "artist"', False, marks=pytest.mark.xfail(
        strict=True, reason='MISSING and PRESENT read "field" as text'), id='missing-quoted'),
    pytest.param('PRESENT "artist"', True, marks=pytest.mark.xfail(
        strict=True, reason='MISSING and PRESENT read "field" as text'), id='present-quoted'),
])
def test_missing_and_present_read_fields(matches, expression, expected):
    assert matches(expression, **BONGO) is expected


@pytest.mark.xfail(strict=True, reason='MISSING is False for a file without tags')
def test_missing_and_present_on_a_file_without_tags(matches):
    # "MISSING field: Evaluates to True if field is not present in a file."
    # A file with no tags at all lacks every field.
    assert matches('MISSING artist') is True
    assert matches('PRESENT artist') is False
