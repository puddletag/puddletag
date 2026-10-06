"""The scripting language: findfunc.parsefunc and the $functions.

Expected results come from three places, named next to each case:
- docs: docsrc/source/scripting.txt and function.txt, the documented behaviour;
- shared: scripts users posted in the puddletag tracker or published in
  their configs (linked);
- bug: reports in the tracker, with the input and expectation they gave.
Tag values are synthetic unless the linked source gave them.

Where the code disagrees with the docs, the case is a strict xfail that says
what differs, so it starts failing once either side is fixed.
"""
import pytest

from puddlestuff import functions
from puddlestuff.audioinfo import INFOTAGS
from puddlestuff.findfunc import ParseError, parsefunc

GH = 'https://github.com/puddletag/puddletag'


def doc_mismatch(reason, **kwargs):
    return pytest.mark.xfail(strict=True, reason=f'code differs from the docs: {reason}', **kwargs)


def run(script, state=None, **tags):
    """Evaluate script against tags shaped like a real Tag's: file-info fields
    (__ext, __path, ...) are strings, every other field is a list of values."""
    m_audio = {k: v if isinstance(v, list) or k in INFOTAGS else [v] for k, v in tags.items()}
    return parsefunc(script, m_audio, state=state)


def truth(expr):
    """Wrap a comparison so the test checks its truth value, which is what the
    docs specify, rather than how True/False happen to be spelled."""
    return f'$if({expr},yes,no)'


# docs: the rules at the top of scripting.txt -----------------------------------

@pytest.mark.parametrize('script, expected', [
    ('$if(0,yes,no)', 'no'),             # 0 evaluates to False
    ('$if(,yes,no)', 'no'),              # an empty string evaluates to False
    ('$if(abc,yes,no)', 'yes'),          # everything else evaluates to True
    ('$lower("Rock, Paper")', 'rock, paper'),  # commas only inside double quotes
    ('$left(" One space.", 3)', ' On'),  # the docs' own example
    ('$upper(   ab)', 'AB'),             # leading whitespace is dropped
    ('$upper(ab   )', 'AB   '),          # ... trailing whitespace is kept
    (r'$upper(a\,b)', 'A,B'),            # a backslash makes , ( ) $ \ literal
    (r'$upper(a\(b\))', 'A(B)'),
    (r'$lower(A\B)', r'a\b'),            # before anything else it is kept
    (r'$upper("a\(b\)")', r'A\(B\)'),    # and in quotes every backslash is kept
    (r'$upper("say \"hi, there\"")', 'SAY "HI, THERE"'),  # except \", a quote
    (r'$upper("a\")', 'A\\'),            # ... unless it ends the argument
    (r'$upper("a\\")', r'A\\'),
    (r'$upper("a\" )', 'A\\ '),
    (r'$replace(a\b,"\",/)', 'a/b'),     # synthetic: replacing backslashes
])
def test_documented_rules(script, expected):
    assert run(script) == expected


# docs: one or more cases per function in scripting.txt -------------------------

@pytest.mark.parametrize('script, expected', [
    (truth('$and(1,1)'), 'yes'),
    (truth('$and(1,0)'), 'no'),
    ('$add(2,3)', '5'),
    ('$add(1.5,2)', '3.5'),
    ('$caps(hello wORLD)', 'Hello World'),
    ('$caps2(hello wORLD)', 'Hello WORLD'),
    ('$caps3(hello wORLD)', 'Hello world'),
    ('$ceiling(2.1)', '3'),
    ('$ceiling(2)', '2'),
    ('$ceiling(-2.5)', '-2'),
    ('$char(A)', '65'),
    ('$div(10,4)', '2.5'),
    (truth('$equals(abc,abc)'), 'yes'),
    (truth('$equals(abc,ABC)'), 'no'),   # x == y is case-sensitive
    ('$find(hello,l)', '2'),
    ('$find(hello,z)', '-1'),
    ('$floor(2.7)', '2'),
    ('$floor(-2.5)', '-3'),
    (truth('$geql(2,2)'), 'yes'),
    (truth('$geql(1,2)'), 'no'),
    (truth('$grtr(10,9)'), 'yes'),
    (truth('$grtr(2,2)'), 'no'),
    ('$if(1,y,z)', 'y'),
    ('$if(0,y,z)', 'z'),
    ('$iflonger(abc,ab,x,y)', 'x'),
    ('$iflonger(ab,abc,x,y)', 'y'),
    (truth('$isdigit(12)'), 'yes'),
    (truth('$isdigit(1.5)'), 'yes'),
    (truth('$isdigit(abc)'), 'no'),
    ('$left(abcdef,2)', 'ab'),
    ('$len(hello)', '5'),
    (truth('$leql(2,2)'), 'yes'),
    (truth('$leql(3,2)'), 'no'),
    (truth('$less(1,2)'), 'yes'),
    (truth('$less(2,2)'), 'no'),
    ('$lower(HeLLo)', 'hello'),
    ('$mod(7,3)', '1'),
    ('$mul(2,3)', '6'),
    (truth('$neql(a,b)'), 'yes'),
    (truth('$neql(a,a)'), 'no'),
    (truth('$not(0)'), 'yes'),
    (truth('$not(1)'), 'no'),
    ('$num(5,2)', '05'),
    ('$num(5,3)', '005'),
    ('$num(007,2)', '07'),
    (truth('$odd(3)'), 'yes'),
    (truth('$odd(4)'), 'no'),
    (truth('$or(0,1)'), 'yes'),
    (truth('$or(0,0)'), 'no'),
    ('$regex(Jay Z,jay,Shawn)', 'Shawn Z'),     # matchcase defaults to 0
    ('$regex(Jay Z,jay,Shawn,1)', 'Jay Z'),     # matchcase=1 is case-sensitive
    ('$regex(abc,"(b)","$upper($1)")', 'aBc'),  # quoted repl runs after the match
    (r'$re_escape(a.b)', r'a\.b'),
    ('$round(2.4)', '2'),
    ('$round(2.5)', '3'),   # "x if y < 0.5 else x + 1"
    ('$round(0.5)', '1'),   # ... so not half-to-even
    ('$replace(Foo Bar,bar,Baz)', 'Foo Baz'),
    ('$replace(Foo Bar,bar,Baz,1)', 'Foo Bar'),   # matchcase
    ('$replace(barbar bar,bar,X,0,1)', 'barbar X'),  # whole words only
    ('$right(abcdef,2)', 'ef'),
    ('$strip("  padded  ")', 'padded'),
    ('$sub(5,3)', '2'),
    ('$to_ascii(abc äéç цы キウ 藏經)', 'abc aec tsy kiu Cang Jing'),  # the docs' example
    ('$to_num(Track 07 of 12)', '07'),   # the docs' example
    ('$to_num(-1.5 dB)', '-1.5'),        # with its sign and decimals
    ('$to_num(abc)', ''),
    ('$upper(abc)', 'ABC'),
    ('$validate("a/b?c")', 'abc'),   # default chars are removed
    ('$validate(a/b,-)', 'a-b'),     # ... or replaced with y
])
def test_documented_functions(script, expected):
    assert run(script) == expected


@pytest.mark.parametrize('script, tags, expected', [
    ('$meta_sep(artist, " / ")', {'artist': ['A', 'B']}, 'A / B'),
    (r'$meta_sep(artist, "\\")', {'artist': ['A', 'B']}, r'A\\B'),  # quoted: every backslash is kept
    ('$meta_sep(artist, " & ")', {'artist': ['A', 'B']}, 'A & B'),  # the docs' example
    ('$meta_sep(artist, %genre%)', {'artist': ['A', 'B'], 'genre': 'G'}, 'A%genre%B'),  # fields aren't replaced
    ('$meta_sep(artist)', {'artist': ['A', 'B']}, 'A, B'),  # sep defaults to ', '
    ('$meta_sep(artist)', {'artist': 'Solo'}, 'Solo'),
])
def test_documented_multi_value_functions(script, tags, expected):
    assert run(script, **tags) == expected


@pytest.mark.parametrize('script, filename, expected', [
    ('$hasformat(%artist% - %title%)', 'A - T.mp3', 'yes'),   # the docs' example:
    ('$hasformat(%artist% - %title%)', 'Untitled.mp3', 'no'),  # text defaults to the file's name
    ('$hasformat(%artist% - %title%,A - T)', 'Untitled.mp3', 'yes'),
])
def test_hasformat(script, filename, expected):
    assert run(truth(script), __filename=filename) == expected


def test_re_escape_makes_regex_match_literally():
    # The docs' example: strip the album's name, brackets and all, from the title.
    assert run('$regex(%title%,$re_escape(%album%),)', title='Song (Live)', album='(Live)') == 'Song '


def test_rand_is_between_0_and_1():
    assert 0 <= float(run('$rand()')) < 1


# The docs leave these open: does "nth value" and "starting at n" count from 0
# or from 1? These pin down today's behaviour (0-based), not a documented one.

def test_meta_index_counts_from_zero():
    assert run('$meta(artist, 1)', artist=['A', 'B']) == 'B'


def test_mid_start_counts_from_zero():
    assert run('$mid(abcdef,1,3)') == 'bcd'


# docs: function.txt, "Replace with RegExp" on 'concentricpuddle writes this'.
# The docs show only the replaced part; the rest of the text stays as it was.

@pytest.mark.parametrize('regex, repl, expected', [
    ('(concentricpuddle)', '$upper($1)', 'CONCENTRICPUDDLE writes this'),
    ('(concentricpuddle) writes (this)', '$upper($1) wrote $2', 'CONCENTRICPUDDLE wrote this'),
    ('(concentricpuddle) writes (this)', '$upper($1) wrote $3', 'CONCENTRICPUDDLE wrote '),
    ('(c.*puddle)', 'name=$1', 'name=concentricpuddle writes this'),
])
def test_documented_replace_with_regexp(regex, repl, expected):
    assert functions.replaceWithReg({}, 'concentricpuddle writes this', regex, repl) == expected


# Synthetic replacements of the kinds users save as actions: a group or the
# whole match passed to a function, optional groups that match nothing,
# removals, $N with text around it, and match case. Expected results follow
# the docs above.

@pytest.mark.parametrize('text, regex, repl, matchcase, expected', [
    ('jay-z', r'-(\w)', '-$upper($1)', False, 'jay-Z'),
    ('Track 7 of 12', r'\d+', '$num($1,3)', False, 'Track 007 of 012'),  # no groups: $1 is the match
    ('one, two, three', r'(\w+),', '$upper($0)', False, 'ONE, TWO, three'),
    ('x-y-z', r'(-[a-z])?', '$upper($1)', False, 'x-Y-Z'),
    ('song (live)', r'\((\w)', '$upper($0)', False, 'song (Live)'),
    ('Vol.2', r'(\w)\.(\w)', '$1. $2', False, 'Vol. 2'),
    ('Song [Demo Version]', r'\s*[\[(](live|demo)( version)?[\])]', '', False, 'Song'),
    ('dj DJ Dj', 'dj', '$upper($0)', True, 'DJ DJ Dj'),
    ('dj DJ Dj', 'dj', '$upper($0)', False, 'DJ DJ DJ'),
    ('A  B   C', r'\s{2,}', ' ', False, 'A B C'),
    ('x!y', '(!)', '$1 ', False, 'x! y'),
    ("it'S", "'([a-z])", "'$lower($1)", False, "it's"),
])
def test_replace_with_regexp(text, regex, repl, matchcase, expected):
    assert functions.replaceWithReg({}, text, regex, repl, matchcase) == expected


# Inside a function call's arguments the matched text is still read as
# script: a % in it starts a field name, and a lone " a quoted string.
GROUP_PARSED_IN_ARGUMENTS = pytest.mark.xfail(
    strict=True, reason="matched text inside a function call's arguments is still parsed")


@pytest.mark.parametrize('text, repl, expected', [
    ('say "hi"', '[$1]', '[say "hi"]'),
    ('50% off 20%', '[$1]', '[50% off 20%]'),
    ('$lower(X)', '[$1]', '[$lower(X)]'),
    ('a,b', '[$1] $lower(X)', '[a,b] x'),
    ('a\\b', '[$1] $lower(X)', '[a\\b] x'),
    ('a)b', '$upper($1)', 'A)B'),
    ('$lower(X)', '$upper($1)', '$LOWER(X)'),
    ('a)b', '$if(1,$upper($1),)', 'A)B'),
    ('a,b', '$upper("$1")', 'A,B'),
    ('a\\b', '$upper("$1")', 'A\\B'),
    ('say "hi"', '$upper("$1")', 'SAY "HI"'),
    pytest.param('50% off 20%', '$upper($1)', '50% OFF 20%', marks=GROUP_PARSED_IN_ARGUMENTS),
    pytest.param('5" disc', '$upper($1)', '5" DISC', marks=GROUP_PARSED_IN_ARGUMENTS),
])
def test_regex_group_is_text_not_script(text, repl, expected):
    # Synthetic. A group is the matched text, wherever its $N is, as I241's
    # reporter expected.
    assert functions.replaceWithReg({}, text, '(.+)', repl) == expected


# shared: scripts users posted in the tracker or their configs ------------------

@pytest.mark.parametrize('script, tags, expected', [
    pytest.param(  # disc folder only for multi-disc releases
        '$if($grtr(%disctotal%,1),Disc %discnumber%,.)',
        {'disctotal': '2', 'discnumber': '1'}, 'Disc 1',
        id='D1028-multi-disc'),
    pytest.param(
        '$if($grtr(%disctotal%,1),Disc %discnumber%,.)',
        {'disctotal': '1', 'discnumber': '1'}, '.',
        id='D1028-single-disc'),
    pytest.param(
        '%albumartist%/%album%/$num(%discnumber%,2)-$num(%track%,2) - %title%',
        {'albumartist': 'Band', 'album': 'LP', 'discnumber': '1', 'track': '3', 'title': 'Song'},
        'Band/LP/01-03 - Song',
        id='D1028-path'),
    pytest.param(
        '%artist%/$if(%series%,%series%/,)%album%/%title%',
        {'artist': 'A', 'series': 'S', 'album': 'Al', 'title': 'T'}, 'A/S/Al/T',
        id='D655-with-series'),
    pytest.param(
        '%artist%/$if(%series%,%series%/,)%album%/%title%',
        {'artist': 'A', 'album': 'Al', 'title': 'T'}, 'A/Al/T',
        id='D655-without-series'),
    pytest.param(  # "convert s01e01 to %disc% %track%"
        '%artist% - s$num(%disc%,2)e$num(%track%,2) - %title%',
        {'artist': 'Show', 'disc': '1', 'track': '2', 'title': 'Pilot'}, 'Show - s01e02 - Pilot',
        id='I405-episode'),
    pytest.param(
        '$if($not($neql(%__ext%,flac)),HQ/%artist% - %title%,Compressed/%track% - %title%)',
        {'__ext': 'flac', 'artist': 'A', 'track': '1', 'title': 'T'}, 'HQ/A - T',
        id='I359-flac'),
    pytest.param(
        '$if($not($neql(%__ext%,flac)),HQ/%artist% - %title%,Compressed/%track% - %title%)',
        {'__ext': 'mp3', 'artist': 'A', 'track': '1', 'title': 'T'}, 'Compressed/1 - T',
        id='I359-mp3'),
    pytest.param(  # artistsort from a multi-valued artist
        '$upper($to_ascii($meta_sep(artist,/)))',
        {'artist': ['Björk', 'Sigur Rós']}, 'BJORK/SIGUR ROS',
        id='I510-artistsort'),
    pytest.param(  # a saved pattern in github.com/xeruf/dotfiles .config/puddletag/puddletag.conf
        '$meta_sep(artist," & ") - %title%',
        {'artist': ['A', 'B'], 'title': 'T'}, 'A & B - T',
        id='xeruf-dotfiles-meta-sep'),
    pytest.param(  # the working script from the issue's last comment
        r'$if(%discnumber%, %discnumber% - ,)$num(%track%,2) - %title%'
        r'$if($replace(%artist%, %albumartist%,),\ - %artist%,)',
        {'discnumber': '1', 'track': '3', 'title': 'Song', 'artist': 'Band', 'albumartist': 'Band'},
        '1 - 03 - Song',
        id='I664-same-artist'),
])
def test_shared_scripts(script, tags, expected):
    assert run(script, **tags) == expected


def test_shared_counter_padding():
    # I618/D572: zero-padding the autonumbering counter
    assert run('$num(%__counter%,2) - %artist% - %title%', state={'__counter': '3'},
               artist='A', title='T') == '03 - A - T'


def test_unknown_function_is_a_syntax_error():
    # D765 used $last_instance, an Mp3tag function puddletag doesn't have.
    with pytest.raises(ParseError, match='function does not exist'):
        run('$last_instance(%title%, "[")', title='Song [Live]')


# bug: reports in the tracker ---------------------------------------------------

def test_replace_quoted_word_keeps_its_spaces():
    # I986: the reporter wanted "Foo / Bar" -> "Foo-Bar"; quoting the word works.
    assert run('$replace(%artist%," / ",-)', artist='Foo / Bar') == 'Foo-Bar'


def test_replace_unquoted_word_keeps_its_trailing_space():
    # I986, unquoted: the leading space is dropped and the trailing one kept,
    # so the word replaced is "/ ".
    assert run('$replace(%artist%, / ,-)', artist='Foo / Bar') == 'Foo -Bar'


def test_unclosed_function_is_a_syntax_error():
    # I970: backspacing the closing bracket crashed puddletag with IndexError.
    with pytest.raises(ParseError, match='No closing bracket'):
        run('%artist% - $num(%track%,2 - %title%', artist='A', track='1', title='T')


def test_sub_accepts_zero():
    # I220: "$sub(3,0)" raised "At least 2 arguments expected".
    assert run('$sub(3,0)') == '3'


def test_validate_accepts_slash_as_bad_char():
    # I197: "$validate(%title%,-,/)" raised "No closing bracket found."
    assert run('$validate(%title%,-,/)', title='AC/DC') == 'AC-DC'


def test_regex_with_escaped_brackets_quoted():
    # I219: removing "(...)" from a title. Quoted, the regex reaches re intact.
    assert run(r'$regex(%title%,"\([\s\S]*\)",)', title='Song (Live)') == 'Song '


@pytest.mark.parametrize('script', [
    r'$regex(%title%,\(.*\),)',          # the docs' example
    r'$regex(%title%,\([\s\S]*\),)',     # the exact script from I219
])
def test_regex_with_escaped_brackets_unquoted(script):
    # docs: unquoted, \( reaches the regex as (, so it matches the whole title.
    assert run(script, title='Song (Live)') == ''


def test_regex_groups_unquoted_need_escaped_closing_parenthesis():
    # docs: the example, and the bare form it warns about.
    assert run(r'$regex(%title%,(.*\) - (.*\),$2 by $1)', title='Artist - Song') == 'Song by Artist'
    with pytest.raises(ParseError):
        run('$regex(%title%,(.*) - (.*),$2 by $1)', title='Artist - Song')


@pytest.mark.parametrize('text, expected', [
    ('Моя цыганиада', 'Moia tsyganiada'),  # I723: Cyrillic came out as "( )"
    ('‘a’ “b”', '\'a\' "b"'),              # I653: smart quotes were dropped
])
def test_to_ascii_transliterates(text, expected):
    assert run(f'$to_ascii({text})') == expected


@pytest.mark.parametrize('text, expected', [
    ('藏經 Live', 'Cang Jing Live'),  # a space follows: no double space
    ('藏經Live', 'Cang Jing Live'),   # a word follows: the space separates them
    ('(藏經)', '(Cang Jing)'),        # punctuation follows
    ('藏 - 經', 'Cang - Jing'),       # the text's own spaces stay
])
def test_to_ascii_adds_no_spaces_after_ideographs(text, expected):
    # Synthetic. unidecode ends each ideograph with a space ("藏" -> "Cang ").
    # The docs' example shows none at the end of the text.
    assert run(f'$to_ascii("{text}")') == expected


def test_regex_matchcase_argument():
    # I335: $regex took at most 3 arguments, so matchcase couldn't be set.
    assert run('$regex(%artist%, "XyZ", "aaa", 1)', artist='xyz') == 'xyz'
    assert run('$regex(%artist%, "XyZ", "aaa")', artist='xyz') == 'aaa'


@pytest.mark.parametrize('function', ['lower', 'strip'])
def test_field_with_comma_is_not_truncated(function):
    # I251 ($lower) and I249 ($strip), both still open: a comma in the field's
    # value cut off everything after it.
    title = 'Eagle Rock Me, Baby'
    assert run(f'${function}(%title%)', title=title) == getattr(str, function)(title)


@pytest.mark.parametrize('replacement', [
    '$1 $upper($2) $3',               # the report
    '$if(1=1,$1,$1) $upper($2) $3',   # a commenter's workaround
])
def test_regex_group_with_comma_next_to_function_call(replacement):
    # I941: a group containing a comma gained a backslash when the replacement
    # also called a function on another group. Text and script from the report.
    title = 'String Quartet no.1 in A major, op.2 i Adante - Allegro'
    script = rf'$regex(%title%, "(.+)\s(i*v*x*i*)\s(.*)", "{replacement}")'
    assert run(script, title=title) == 'String Quartet no.1 in A major, op.2 I Adante - Allegro'


@pytest.mark.parametrize('text, regex, repl, expected', [
    ('Attack, at dawn.', r'(, )(\w)', '$1$caps($2)', 'Attack, At dawn.'),    # the report
    ('Attack, at dawn.', r'(, )(\w)', '$caps($1$2)', 'Attack, At dawn.'),    # its workaround
    ('(Attack, at dawn.', r'(, )(\w)', '$caps($1$2)', '(Attack, At dawn.'),  # ... with a "("
    ('Attack " \\ , at dawn.', r'(.+)(\w)', '$1$caps($2)', 'Attack " \\ , at dawN.'),
])
def test_regex_replace_keeps_group_text(text, regex, repl, expected):
    # I241 and its comments: inputs and expected outputs from the reporter.
    assert functions.replaceWithReg({}, text, regex, repl) == expected


def test_regex_removes_leading_dots():
    # I382: the regex suggested in the thread for "...And justice for all."
    assert functions.replaceWithReg({}, '...And justice for all.', r'^\.{3}', '') \
        == 'And justice for all.'
