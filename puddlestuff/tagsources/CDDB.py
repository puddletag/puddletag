# Module for retrieving CDDB v1 data from CDDB servers via HTTP

# Written 17 Nov 1999 by Ben Gertzfield <che@debian.org>
# This work is released under the GNU GPL, version 2 or later.

# Release version 1.4
# CVS ID: $Id: CDDB.py,v 1.8 2003/08/31 23:18:43 che_fox Exp $

import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

name = 'CDDB.py'
version = 1.4

if 'EMAIL' in os.environ:
    (default_user, hostname) = os.environ['EMAIL'].split('@')
else:
    default_user = os.geteuid() or os.environ.get('USER') or 'user'
    hostname = socket.gethostname() or 'host'

# Use protocol version 5 to get DYEAR and DGENRE fields.
proto = 5
default_server = 'http://gnudb.gnudb.org/~cddb/cddb.cgi'
escapes = {'\\': '\\', 'n': '\n', 't': '\t'}


def _decode(raw):
    # Level 6 is UTF-8, but the format also allows ISO-8859-1, so a line that
    # isn't UTF-8 is read as that. Below level 6 it is always ISO-8859-1.
    if proto >= 6:
        try:
            return raw.decode()
        except UnicodeDecodeError:
            pass
    return raw.decode('latin-1')


def query(track_info, server_url=None,
          user=None, host=None, client_name=name,
          client_version=version):
    if server_url is None:
        server_url = default_server
    if user is None:
        user = default_user
    if host is None:
        host = hostname

    disc_id = track_info[0]
    num_tracks = track_info[1]

    query_str = (('%08lx %d ') % (disc_id, num_tracks))

    for i in track_info[2:]:
        query_str = query_str + ('%d ' % i)

    url = "%s?%s" % (server_url, urllib.parse.urlencode({
        'cmd': 'cddb query ' + query_str.rstrip(),
        'hello': ' '.join(str(word) for word in (user, host, client_name, client_version)),
        'proto': proto}))

    response = urllib.request.urlopen(url)

    # Four elements in header: status, category, disc-id, title
    header = _decode(response.readline()).rstrip().split(' ', 3)

    header[0] = int(header[0])

    if header[0] == 200:  # OK
        result = {'category': header[1], 'disc_id': header[2], 'title':
            header[3]}

        return [header[0], result]

    elif header[0] == 211 or header[0] == 210:  # multiple matches
        result = []

        for line in response.readlines():
            line = _decode(line).rstrip()

            if line == '.':  # end of matches
                break
                # otherwise:
                # split into 3 pieces, not 4
                # (thanks to bgp for the fix!)
            match = line.split(' ', 2)

            result.append({'category': match[0], 'disc_id': match[1], 'title':
                match[2]})

        return [header[0], result]

    else:
        return [header[0], None]


def read(category, disc_id, server_url=None,
         user=None, host=None, client_name=name,
         client_version=version):
    if server_url is None:
        server_url = default_server
    if user is None:
        user = default_user
    if host is None:
        host = hostname

    url = "%s?%s" % (server_url, urllib.parse.urlencode({
        'cmd': 'cddb read %s %s' % (category, disc_id),
        'hello': ' '.join(str(word) for word in (user, host, client_name, client_version)),
        'proto': proto}))

    response = urllib.request.urlopen(url)

    header = _decode(response.readline()).rstrip().split(' ', 3)

    header[0] = int(header[0])
    if header[0] == 210 or header[0] == 417:  # success or access denied
        reply = []

        for line in response.readlines():
            line = _decode(line).rstrip('\r\n')

            if line == '.':
                break

            reply.append(line)

        if header[0] == 210:  # success, parse the reply
            return [header[0], parse_read_reply(reply)]
        else:  # access denied. :(
            return [header[0], reply]
    else:
        return [header[0], None]


def parse_read_reply(comments):
    len_re = re.compile(r'#\s*Disc length:\s*(\d+)\s*seconds')
    revis_re = re.compile(r'#\s*Revision:\s*(\d+)')
    submit_re = re.compile(r'#\s*Submitted via:\s*(.+)')
    keyword_re = re.compile(r'([^=]+)=(.*)')

    result = {}

    keywords = []

    for line in comments:
        if not line.startswith('#'):
            keyword_match = keyword_re.match(line)
            if keyword_match:
                (keyword, data) = keyword_match.groups()

                if keyword in result:
                    result[keyword] = result[keyword] + data
                else:
                    result[keyword] = data
                    keywords.append(keyword)
            continue

        len_match = len_re.match(line)
        if len_match:
            result['disc_len'] = int(len_match.group(1))
            continue

        revis_match = revis_re.match(line)
        if revis_match:
            result['revision'] = int(revis_match.group(1))
            continue

        submit_match = submit_re.match(line)
        if submit_match:
            result['submitted_via'] = submit_match.group(1)
            continue

    # Translated once the lines are joined, so an escape can span two lines.
    for keyword in keywords:
        result[keyword] = re.sub(r'\\([\\nt])', lambda m: escapes[m.group(1)], result[keyword])

    return result
