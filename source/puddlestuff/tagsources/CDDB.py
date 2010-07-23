
# Module for retrieving CDDB v1 data from CDDB servers via HTTP

# Written 17 Nov 1999 by Ben Gertzfield <che@debian.org>
# This work is released under the GNU GPL, version 2 or later.

# Release version 1.4
# CVS ID: $Id: CDDB.py,v 1.8 2003/08/31 23:18:43 che_fox Exp $

import urllib, string, socket, os, struct, re

name = 'CDDB.py'
version = 1.4

if os.environ.has_key('EMAIL'):
    (default_user, hostname) = string.split(os.environ['EMAIL'], '@')
else:
    default_user = os.geteuid() or os.environ['USER'] or 'user'
    hostname = socket.gethostname() or 'host'

# Use protocol version 5 to get DYEAR and DGENRE fields.
proto = 5
default_server = 'http://freedb.freedb.org/~cddb/cddb.cgi'

def query(track_info, server_url=default_server,
	  user=default_user, host=hostname, client_name=name,
          client_version=version):

    disc_id = track_info[0]
    num_tracks = track_info[1]

    query_str = (('%08lx %d ') % (disc_id, num_tracks))

    for i in track_info[2:]:
	query_str = query_str + ('%d ' % i)
	
    query_str = urllib.quote_plus(string.rstrip(query_str))

    url = "%s?cmd=cddb+query+%s&hello=%s+%s+%s+%s&proto=%i" % \
	  (server_url, query_str, user, host, client_name,
           client_version, proto)

    response = urllib.urlopen(url)
    
    # Four elements in header: status, category, disc-id, title
    header = string.split(string.rstrip(response.readline()), ' ', 3)

    header[0] = string.atoi(header[0])

    if header[0] == 200:		# OK
	result = { 'category': header[1], 'disc_id': header[2], 'title':
		   header[3] }

	return [ header[0], result ]

    elif header[0] == 211 or header[0] == 210: # multiple matches
	result = []

	for line in response.readlines():
	    line = string.rstrip(line)

	    if line == '.':		# end of matches
		break
					# otherwise:
					# split into 3 pieces, not 4
					# (thanks to bgp for the fix!)
	    match = string.split(line, ' ', 2)

	    result.append({ 'category': match[0], 'disc_id': match[1], 'title':
			    match[2] })

	return [ header[0], result ]

    else:
	return [ header[0], None ]

def read(category, disc_id, server_url=default_server, 
	 user=default_user, host=hostname, client_name=name,
         client_version=version):

    url = "%s?cmd=cddb+read+%s+%s&hello=%s+%s+%s+%s&proto=%i" % \
	  (server_url, category, disc_id, user, host, client_name,
           client_version, proto)

    response = urllib.urlopen(url)
    
    header = string.split(string.rstrip(response.readline()), ' ', 3)

    header[0] = string.atoi(header[0])
    if header[0] == 210 or header[0] == 417: # success or access denied
	reply = []

	for line in response.readlines():
	    line = string.rstrip(line)

	    if line == '.':
		break;

	    line = string.replace(line, r'\t', "\t")
	    line = string.replace(line, r'\n', "\n")
	    line = string.replace(line, r'\\', "\\")

	    reply.append(line)

	if header[0] == 210:		# success, parse the reply
	    return [ header[0], parse_read_reply(reply) ]
	else:				# access denied. :(
	    return [ header[0], reply ]
    else:
	return [ header[0], None ]

def parse_read_reply(comments):
    
    len_re = re.compile(r'#\s*Disc length:\s*(\d+)\s*seconds')
    revis_re = re.compile(r'#\s*Revision:\s*(\d+)')
    submit_re = re.compile(r'#\s*Submitted via:\s*(.+)')
    keyword_re = re.compile(r'([^=]+)=(.*)')

    result = {}

    for line in comments:
	keyword_match = keyword_re.match(line)
	if keyword_match:
	    (keyword, data) = keyword_match.groups()

	    if result.has_key(keyword):
		result[keyword] = result[keyword] + data
	    else:
		result[keyword] = data
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

    return result
