"""Filter expressions (puddlestuff/audio_filter.py), run on real files the way
the Filter panel runs them (tagmodel.py applyFilter).

Expected results come from docsrc/source/filter.txt unless noted. Tags are
synthetic, the docs' own example values where they give them. On a fresh
profile, the fields the filter knows are audioinfo's default field list.
"""
import pytest

from puddlestuff import audioinfo
from puddlestuff.audio_filter import parse

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
    pytest.param('"Bongo Maffin"', BONGO, True, id='quoted-words',
                 marks=pytest.mark.xfail(strict=True, reason='a quoted search keeps its quotes, so it finds nothing')),
    pytest.param('MISSING artist', BONGO, False, id='missing'),
    pytest.param('MISSING style', BONGO, True, id='missing-absent'),
    pytest.param('PRESENT artist', BONGO, True, id='present'),
    pytest.param('PRESENT style', BONGO, False, id='present-absent'),
    # GREATER/LESS: "Conversion to floats will be attempted first": as text,
    # "9" isn't less than "10".
    pytest.param('track LESS 10', dict(BONGO, tracknumber='9'), True, id='less-numbers'),
    pytest.param('track GREATER 10', dict(BONGO, tracknumber='9'), False, id='greater-numbers'),
    pytest.param('artist LESS "some words"', BONGO, True, id='less-text'),
    pytest.param('artist GREATER "some words"', BONGO, False, id='greater-text'),
    # "All comparisons are case-insensitive"
    pytest.param('artist GREATER "a"', BONGO, True, id='greater-text-case',
                 marks=pytest.mark.xfail(strict=True, reason='GREATER and LESS compare text case-sensitively')),
    pytest.param('track EQUAL 5', BONGO, True, id='equal-numbers',
                 marks=pytest.mark.xfail(strict=True, reason="EQUAL compares as text: '05' isn't '5'")),
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


DOCUMENTED_FIELD_UNKNOWN = pytest.mark.xfail(
    strict=True, reason='albumartist, a documented field missing from the default field list, '
                        'is read as the text "albumartist" (#1026)')


@pytest.mark.parametrize('expression, tags, expected', [
    # #638: filters that "filter nothing"; synthetic values.
    pytest.param('%title% IS "at"', {'title': 'At'}, True, id='I638-is'),
    pytest.param('%genre% HAS "DnB"', {'genre': 'Drum & Bass / DnB'}, True, id='I638-has'),
    pytest.param('genre HAS "DnB"', {'genre': 'Drum & Bass / DnB'}, True, id='I638-has-field'),
    # #665, #929: filtering by a single "-" crashed; it's a plain search.
    pytest.param('-', {'title': 'A - B'}, True, id='I929-dash'),
    # #1026: an empty list for albumartist filters, on files whose
    # albumartist is "Various Artists".
    pytest.param('albumartist has "Various"', {'albumartist': 'Various Artists'}, True,
                 id='I1026-has', marks=DOCUMENTED_FIELD_UNKNOWN),
    pytest.param('albumartist IS "Various Artists"', {'albumartist': 'Various Artists'}, True,
                 id='I1026-is', marks=DOCUMENTED_FIELD_UNKNOWN),
    pytest.param('albumartist IS "Various"', {'albumartist': 'Various Artists'}, False, id='I1026-is-part'),
    # #463: "Filtering a field with non-English char" finds nothing; it
    # gives no example, so a synthetic one.
    pytest.param('artist IS "björk"', {'artist': 'Björk'}, True, id='I463-is'),
])
def test_reported_filters(matches, expression, tags, expected):
    assert matches(expression, **tags) is expected


def test_invalid_regex_does_not_crash(matches):
    # #665, #929: a filter the user is still typing must not crash
    # puddletag; it matches nothing. Synthetic expression, missing a "(".
    assert matches('title MATCHES "live)$"', title='Song (Live)') is False
