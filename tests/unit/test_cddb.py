"""The CDDB protocol module (puddlestuff/tagsources/CDDB.py), against replies
a local web server sends back.

Every reply is synthetic, shaped like gnudb's. Expected values come from
the CDDB protocol and the xmcd database format as freedb documented them
(CDDBPROTO and DBFORMAT, kept by the Internet Archive at
web.archive.org/web/2019/http://ftp.freedb.org/pub/freedb/latest/), and from
gnudb's how-to (gnudb.org/howto.php) for what gnudb asks of the hello.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from puddlestuff.tagsources import CDDB

ROOT = Path(__file__).resolve().parents[2]

CGI = '/~cddb/cddb.cgi'
DISC_ID = '0c025603'
# Synthetic: three tracks starting 2, 202 and 402 seconds in, 600 seconds in
# all, under the id the CDDB algorithm gives them.
TRACK_INFO = [0x0c025603, 3, 150, 15150, 30150, 600]
# The protocol's example user and host; the client is synthetic.
HELLO = {'client_name': 'puddletag', 'client_version': '1.0', 'host': 'my.host.com',
         'user': 'joe'}
QUERY = {'cmd': f'cddb query {DISC_ID} 3 150 15150 30150 600'}
READ = {'cmd': f'cddb read rock {DISC_ID}'}
# The environment variables the hello's user name may come from.
USER_VARIABLES = ('EMAIL', 'LNAME', 'LOGNAME', 'USER', 'USERNAME')


@pytest.fixture
def cddb(monkeypatch, web_server):
    """The CGI's address on the local server, at protocol level 6: the level
    freedb sets when it's imported, as the tagsources package always does."""
    monkeypatch.setattr(CDDB, 'proto', 6)
    return web_server.url + CGI


def reply(*lines):
    """A reply's body, each line ending in CR LF as gnudb's do."""
    return ''.join(line + '\r\n' for line in lines)


def entry(*data):
    """A read reply for DISC_ID: the status line, an xmcd file's comments,
    ``data`` (its KEYWORD=data lines) and the terminating marker."""
    return reply(f"210 rock {DISC_ID} CD database entry follows (until terminating `.')",
                 '# xmcd', '#', '# Track frame offsets:', '#\t150', '#\t15150', '#\t30150',
                 '#', '# Disc length: 600 seconds', '#', '# Revision: 3',
                 '# Submitted via: synthclient 1.0', '#', *data, '.')


def served_read(web_server, url, body):
    web_server.add(CGI, body, content_type='text/plain', query=READ)
    return CDDB.read('rock', DISC_ID, server_url=url, **HELLO)


def served_query(web_server, url, body):
    web_server.add(CGI, body, content_type='text/plain', query=QUERY)
    return CDDB.query(TRACK_INFO, server_url=url, **HELLO)


def imported_hello(env, patch=''):
    """The user and host CDDB puts in the hello, as a fresh interpreter
    imports it with only ``env`` among USER_VARIABLES set and the host name
    my.host.com. ``patch`` is code run before the import. A subprocess,
    because reloading CDDB here would reset the protocol level freedb sets."""
    clean = {k: v for k, v in os.environ.items() if k not in USER_VARIABLES}
    code = ('import os, socket; socket.gethostname = lambda: "my.host.com"; ' + patch
            + 'from puddlestuff.tagsources import CDDB; '
            'print(CDDB.default_user, CDDB.hostname, sep="\\n")')
    done = subprocess.run([sys.executable, '-c', code], env={**clean, **env}, cwd=ROOT,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.splitlines()


@pytest.mark.xfail(strict=True, reason="the hello's user is 'user' for root, not its login name")
def test_cddb_imports_as_root_without_user():
    # Synthetic: root in a container, where USER and EMAIL aren't set. The
    # hello's user is "Login name of user".
    assert imported_hello({}, 'os.getuid = os.geteuid = lambda: 0; ') == ['root', 'my.host.com']


def test_read_returns_the_entrys_fields(web_server, cddb):
    # "Multiple occurrences of the same keyword indicate that the data
    # contained on those lines should be concatenated"; "DYEAR ... the
    # (4-digit) year"; the level 5 entries "also contain DYEAR and DGENRE
    # fields". "Disc length", "Revision" and "Submitted via" are the comments
    # applications don't ignore.
    body = entry('DISCID=0c025603', 'DTITLE=Some Artist / Some Album', 'DYEAR=1999',
                 'DGENRE=Ambient', 'TTITLE0=First Track',
                 'TTITLE1=A second title the submitter split over two li', 'TTITLE1=nes',
                 'TTITLE2=Third Track', 'EXTD=', 'EXTT0=', 'EXTT1=', 'EXTT2=', 'PLAYORDER=')

    assert served_read(web_server, cddb, body) == [210, {
        'DGENRE': 'Ambient', 'DISCID': '0c025603', 'DTITLE': 'Some Artist / Some Album',
        'DYEAR': '1999', 'EXTD': '', 'EXTT0': '', 'EXTT1': '', 'EXTT2': '', 'PLAYORDER': '',
        'TTITLE0': 'First Track', 'TTITLE1': 'A second title the submitter split over two lines',
        'TTITLE2': 'Third Track', 'disc_len': 600, 'revision': 3,
        'submitted_via': 'synthclient 1.0'}]


def test_read_keeps_an_equals_sign_in_a_value(web_server, cddb):
    # "data" is any string of "space (20h) through tilde (7Eh) inclusive", and
    # = is in that range.
    body = entry('DISCID=0c025603', 'DTITLE=Some Artist / Some Album', 'TTITLE0=1 + 1 = 2')

    status, data = served_read(web_server, cddb, body)

    assert data['TTITLE0'] == '1 + 1 = 2'


@pytest.mark.parametrize(('value', 'expected'), [
    pytest.param(r'A\\B', r'A\B', id='backslash'),
    pytest.param(r'A\\nB', r'A\nB', id='backslash-then-n'),
    pytest.param(r'C:\\temp', r'C:\temp', id='backslash-then-t'),
    pytest.param(r'A\nB', 'A\nB', id='newline'),
    pytest.param(r'A\tB', 'A\tB', id='tab'),
    # Synthetic: the format names no other escape, so it stays as it is.
    pytest.param(r'A\xB', r'A\xB', id='unknown'),
])
def test_read_translates_escapes(web_server, cddb, value, expected):
    # "Newlines (0Ah), tabs (09h) and backslashes may be represented by the
    # two-character sequences "\n", "\t" and "\\" respectively. Client
    # programs must translate these sequences to the appropriate characters".
    body = entry('DISCID=0c025603', 'DTITLE=Some Artist / Some Album', 'TTITLE0=' + value)

    status, data = served_read(web_server, cddb, body)

    assert data['TTITLE0'] == expected


@pytest.mark.parametrize(('lines', 'expected'), [
    pytest.param([r'EXTD=Recorded live\nMixed in stu', 'EXTD=dio B'],
                 'Recorded live\nMixed in studio B', id='escape-in-a-line'),
    # Synthetic: the format joins the lines, then translates.
    pytest.param(['EXTD=Side one\\', 'EXTD=nSide two'], 'Side one\nSide two',
                 id='escape-split-across-lines'),
])
def test_read_joins_continued_lines_before_translating(web_server, cddb, lines, expected):
    # The format's own example: "EXTD=Copyright (c) 1981 MCA Records
    # Inc.\nManufactured f" and "EXTD=or MCA Records Inc." "should be
    # displayed to the user as: Copyright (c) 1981 MCA Records Inc. /
    # Manufactured for MCA Records Inc."
    body = entry('DISCID=0c025603', 'DTITLE=Some Artist / Some Album', *lines)

    status, data = served_read(web_server, cddb, body)

    assert data['EXTD'] == expected


def test_read_reads_comments_only_as_comments(web_server, cddb):
    # "Lines that begin with # are comments. ... Comments should be ignored by
    # applications", bar "Submitted via: client_name client_version
    # optional_comments", where "optional_comments" is any legal characters,
    # = among them.
    body = reply(f"210 rock {DISC_ID} CD database entry follows (until terminating `.')",
                 '# xmcd', '#', '# Disc length: 600 seconds', '#', '# Revision: 3',
                 '# Processed by: synthserver key=value',
                 '# Submitted via: synthclient 1.0 build=7', '#',
                 'DISCID=0c025603', 'DTITLE=Some Artist / Some Album', '.')

    status, data = served_read(web_server, cddb, body)

    assert (status, data['submitted_via']) == (210, 'synthclient 1.0 build=7')
    assert [key for key in data if key.startswith('#')] == []


@pytest.mark.parametrize(('body', 'expected'), [
    # "401 Specified CDDB entry not found." / "<- code categ discid No such CD
    # entry in database."
    pytest.param(reply('401 rock 0c025603 No such CD entry in database.'), [401, None],
                 id='not-found'),
    # 417 isn't one of read's codes. "4xx Command OK, but cannot be
    # performed" and "x1x More server-to-client output follows (until
    # terminating marker)": the explanation runs up to the ".".
    pytest.param(reply("417 Access limit exceeded, explanation follows (until terminating `.')",
                       'Too many requests from this address today.',
                       'Please try again tomorrow.', '.'),
                 [417, ['Too many requests from this address today.',
                        'Please try again tomorrow.']],
                 id='refused'),
])
def test_read_errors(web_server, cddb, body, expected):
    assert served_read(web_server, cddb, body) == expected


@pytest.mark.parametrize(('body', 'expected'), [
    # "200 Found exact match": "<- code categ discid dtitle"
    pytest.param(reply('200 rock 0c025603 Some Artist / Some Album'),
                 [200, {'category': 'rock', 'disc_id': '0c025603',
                        'title': 'Some Artist / Some Album'}],
                 id='exact'),
    # "210 Found exact matches, list follows (until terminating marker)";
    # synthetic list, in the shape gnudb answers: always category data.
    pytest.param(reply("210 Found exact matches, list follows (until terminating `.')",
                       'data 0c025603 Some Artist / Some Album',
                       'data 0c025604 Some Artist / Some Album (Remastered)', '.'),
                 [210, [{'category': 'data', 'disc_id': '0c025603',
                         'title': 'Some Artist / Some Album'},
                        {'category': 'data', 'disc_id': '0c025604',
                         'title': 'Some Artist / Some Album (Remastered)'}]],
                 id='exact-list'),
    # "211 Found inexact matches, list follows (until terminating marker)"
    pytest.param(reply("211 Found inexact matches, list follows (until terminating `.')",
                       'misc 0c0256ff Other Artist / Other Album',
                       'rock 0c025603 Some Artist / Some Album', '.'),
                 [211, [{'category': 'misc', 'disc_id': '0c0256ff',
                         'title': 'Other Artist / Other Album'},
                        {'category': 'rock', 'disc_id': '0c025603',
                         'title': 'Some Artist / Some Album'}]],
                 id='inexact'),
    # "202 No match found"
    pytest.param(reply('202 No match for disc ID 0c025603.'), [202, None], id='none'),
])
def test_query_replies(web_server, cddb, body, expected):
    assert served_query(web_server, cddb, body) == expected


@pytest.mark.parametrize('proto', [5, 6])
@pytest.mark.parametrize(('call', 'command', 'body'), [
    pytest.param('query', QUERY['cmd'], reply('202 No match for disc ID 0c025603.'), id='query'),
    pytest.param('read', READ['cmd'], reply('401 rock 0c025603 No such CD entry in database.'),
                 id='read'),
])
def test_request_carries_the_command_hello_and_level(web_server, cddb, monkeypatch, proto,
                                                     call, command, body):
    # "cmd=server+command&hello=joe+my.host.com+clientname+version&proto=6";
    # the query's discid is 8 hex digits ("Example: f50a3b13").
    monkeypatch.setattr(CDDB, 'proto', proto)

    if call == 'query':
        served_query(web_server, cddb, body)
    else:
        served_read(web_server, cddb, body)

    assert web_server.requests[-1].query == {
        'cmd': [command],
        'hello': ['joe my.host.com puddletag 1.0'],
        'proto': [str(proto)]}


def test_level_6_reply_is_utf8(web_server, cddb):
    # "Protocol level 6 is the same as level 5 except that the character set
    # is now UTF-8 instead of ISO-8859-1."
    body = entry('DISCID=0c025603', 'DTITLE=Café / Déjà vu', 'TTITLE0=Naïve')

    status, data = served_read(web_server, cddb, body)

    assert (data['DTITLE'], data['TTITLE0']) == ('Café / Déjà vu', 'Naïve')

    body = reply("211 Found inexact matches, list follows (until terminating `.')",
                 'rock 0c025603 Café / Déjà vu', '.')

    status, matches = served_query(web_server, cddb, body)

    assert matches[0]['title'] == 'Café / Déjà vu'


def test_requests_go_to_the_module_defaults(cddb, monkeypatch, web_server):
    monkeypatch.setattr(CDDB, 'default_server', cddb)
    monkeypatch.setattr(CDDB, 'default_user', 'joe')
    monkeypatch.setattr(CDDB, 'hostname', 'my.host.com')
    web_server.add(CGI, reply('202 No match for disc ID 0c025603.'), content_type='text/plain')
    assert CDDB.query(TRACK_INFO) == [202, None]
    assert web_server.requests[-1].query['hello'] == ['joe my.host.com CDDB.py 1.4']


@pytest.mark.parametrize(('user', 'expected'), [
    pytest.param('josé', 'josé my.host.com puddletag 1.0', id='non-ascii'),
    pytest.param('joe+tag', 'joe+tag my.host.com puddletag 1.0', id='plus'),
])
def test_hello_words_are_quoted(web_server, cddb, user, expected):
    # "Special characters may be represented by the sequence "%XX"" and the
    # hello is "username hostname clientname version": five words would break
    # it. A non-ASCII word is sent as its UTF-8 bytes.
    web_server.add(CGI, reply('202 No match for disc ID 0c025603.'),
                   content_type='text/plain', query=QUERY)

    CDDB.query(TRACK_INFO, server_url=cddb, **{**HELLO, 'user': user})

    assert web_server.requests[-1].query['hello'] == [expected]


def test_level_5_reply_is_latin1(web_server, cddb, monkeypatch):
    # "Protocol level 6 is the same as level 5 except that the character set
    # is now UTF-8 instead of ISO-8859-1."
    monkeypatch.setattr(CDDB, 'proto', 5)
    body = entry('DISCID=0c025603', 'DTITLE=Café / Déjà vu', 'TTITLE0=Naïve')

    status, data = served_read(web_server, cddb, body.encode('latin-1'))

    assert (data['DTITLE'], data['TTITLE0']) == ('Café / Déjà vu', 'Naïve')

    body = reply("211 Found inexact matches, list follows (until terminating `.')",
                 'rock 0c025603 Café / Déjà vu', '.')

    status, matches = served_query(web_server, cddb, body.encode('latin-1'))

    assert matches[0]['title'] == 'Café / Déjà vu'


def test_level_6_reply_that_is_not_utf8(web_server, cddb):
    # Synthetic: a level 6 server that still sends ISO-8859-1, which "Database
    # entries must be in the US-ASCII, ISO-8859-1 ... or UTF-8" allows.
    body = entry('DISCID=0c025603', 'DTITLE=Café / Déjà vu', 'TTITLE0=Naïve')

    status, data = served_read(web_server, cddb, body.encode('latin-1'))

    assert (data['DTITLE'], data['TTITLE0']) == ('Café / Déjà vu', 'Naïve')


def test_read_keeps_the_space_where_a_line_was_split(web_server, cddb):
    # "Multiple occurrences of the same keyword indicate that the data
    # contained on those lines should be concatenated"
    body = entry('DISCID=0c025603', 'TTITLE0=Part one of a long ', 'TTITLE0=title')

    status, data = served_read(web_server, cddb, body)

    assert data['TTITLE0'] == 'Part one of a long title'


@pytest.mark.parametrize(('email', 'expected'), [
    pytest.param('Joe Bloggs <joe@my.host.com>', ['joe', 'my.host.com'], id='display-name',
                 marks=pytest.mark.xfail(strict=True, reason='gives "Joe Bloggs <joe"')),
    pytest.param('joe@my.host.com', ['joe', 'my.host.com'], id='bare'),
])
def test_hello_names_come_from_an_email_address(email, expected):
    # gnudb "requires a valid email" and its example hello is "emailname+emailhost.com+
    # applicationname+0.1": the user and host are the address's two sides.
    assert imported_hello({'EMAIL': email, 'USER': 'johndoe'}) == expected


@pytest.mark.parametrize('email', [
    pytest.param('', id='empty'),
    pytest.param('joe', id='no-at-sign'),
    pytest.param('joe@a@b', id='two-at-signs'),
])
@pytest.mark.xfail(strict=True, reason='the import raises ValueError, so puddletag cannot start')
def test_hello_user_is_the_login_name_when_email_is_no_address(email):
    # "username: Login name of user. Example: johndoe"
    assert imported_hello({'EMAIL': email, 'USER': 'johndoe'}) == ['johndoe', 'my.host.com']


@pytest.mark.xfail(strict=True, reason='gives the numeric user id')
def test_hello_user_is_the_login_name():
    # "username: Login name of user. Example: johndoe"
    assert imported_hello({'USER': 'johndoe'}) == ['johndoe', 'my.host.com']


@pytest.mark.xfail(strict=True, reason='gives the numeric user id')
def test_hello_user_without_a_login_name():
    # Synthetic: a user id with no password entry, as in a container started
    # with --user 4242.
    assert imported_hello({}, 'os.getuid = os.geteuid = lambda: 4242; ') == ['user', 'my.host.com']
