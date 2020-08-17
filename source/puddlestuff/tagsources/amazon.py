# -*- coding: utf-8 -*-
# Example tutorial for writing a tag source plugin using Amazon's webservice API.

# The important stuff is at the bottom in the Amazon class.
# Comments (or you've created a tag source you'd like
# to share) can be directed at concentricpuddle@gmail.com

import base64
import hashlib
import hmac
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from xml.dom import minidom

from ..audioinfo import DATA
from ..constants import CHECKBOX, COMBO, TEXT
from ..tagsources import (write_log, RetrievalError,
                          urlopen, parse_searchstring)
from ..util import translate

default_access_key = base64.b64decode('QUtJQUozS0JZUlVZUU41UFZRR0E=')
default_secret_key = base64.b64decode('dmh6Q0ZaSEF6N0VvMmN5REt3STVnS1liU3ZFTCtSckx3c0tmanZEdA==')

access_key = default_access_key
secret_key = default_secret_key

SMALLIMAGE = '#smallimage'
MEDIUMIMAGE = '#mediumimage'
LARGEIMAGE = '#largeimage'

image_types = [SMALLIMAGE, MEDIUMIMAGE, LARGEIMAGE]

XMLKEYS = {
    'Artist': 'artist',
    'Label': 'label',
    'ReleaseDate': 'year',
    'Title': 'album',
    "Publisher": 'publisher'}

IMAGEKEYS = {'SmallImage': SMALLIMAGE,
             'MediumImage': MEDIUMIMAGE,
             'LargeImage': LARGEIMAGE}


def check_binding(node):
    """Checks whether a returned item as an Audio CD."""
    try:
        binding = node.getElementsByTagName('Binding')[0].firstChild.data
        return binding == 'Audio CD'
    except IndexError:
        return


def create_aws_url(aws_access_key_id, secret, query_dictionary):
    """Creates the query url that'll be used to query Amazon's service."""
    query_dictionary["AWSAccessKeyId"] = aws_access_key_id
    query_dictionary["Timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime())

    items = [(key, value) for key, value in
             query_dictionary.items()]
    query = urllib.parse.urlencode(sorted(items))

    try:
        hm = hmac.new(secret, "GET\nwebservices.amazon.com\n/onca/xml\n" \
                      + query, hashlib.sha256)
    except TypeError:
        raise RetrievalError(translate('Amazon',
                                       'Invalid Access or Secret Key'))
    signature = urllib.parse.quote(base64.b64encode(hm.digest()))

    query = "http://webservices.amazon.com/onca/xml?%s&Signature=%s" % (
        query, signature)
    return query


def check_matches(albums, artist=None, album_name=None):
    ret = []
    if artist and album_name:
        album_name = album_name.lower()
        artist = artist.lower()

        ret = [album for album in albums if
               album_name in album.get('album', album_name).lower() and
               artist in album.get('artist', artist).lower()]
    elif artist:
        artist = artist.lower()
        ret = [
            album for album in albums if
            artist in album.get('artist', artist).lower()
        ]
    elif album_name:
        album_name = album_name.lower()
        ret = [
            album for album in albums if
            album_name in album.get('album', album).lower()
        ]

    return ret if ret else albums


def get_asin(node):
    """Retrieves the ASIN of a node."""
    return node.getElementsByTagName('ASIN')[0].firstChild.data


def get_image_url(node):
    return node.getElementsByTagName('URL')[0].firstChild.data


def get_site_url(node):
    return node.getElementsByTagName('DetailPageURL')[0].firstChild.data


def get_text(node):
    """Returns the textual data in a node."""
    return node.firstChild.data


def keyword_search(keywords):
    write_log(translate('Amazon',
                        'Retrieving search results for keywords: %s') % keywords)
    query_pairs = {
        "Operation": "ItemSearch",
        'SearchIndex': 'Music',
        "ResponseGroup": "ItemAttributes,Images",
        "Service": "AWSECommerceService",
        'ItemPage': '1',
        'Keywords': keywords,
        'AssociateTag': 'puddletag-20'}
    url = create_aws_url(access_key, secret_key, query_pairs)
    xml = urlopen(url)
    return parse_search_xml(xml)


def parse_album_xml(text, album=None):
    """Parses the retrieved xml for an album and get's the track listing."""
    doc = minidom.parseString(text)
    album_item = doc.getElementsByTagName('Item')[0]
    try:
        tracklist = album_item.getElementsByTagName('Tracks')[0]
    except IndexError:
        write_log(translate('Amazon',
                            'No tracks found in listing.'))
        write_log(text)
        return None
    tracks = []
    discs = [disc for disc in tracklist.childNodes if
             not disc.nodeType == disc.TEXT_NODE]
    if not (len(discs) > 1 and album):
        album = None
    for discnum, disc in enumerate(discs):
        for track_node in disc.childNodes:
            if track_node.nodeType == track_node.TEXT_NODE:
                continue
            title = get_text(track_node)
            tracknumber = track_node.attributes['Number'].value
            if album:
                tracks.append({'track': tracknumber, 'title': title,
                               'album': '%s (Disc %s)' % (album, discnum + 1)})
            else:
                tracks.append({'track': tracknumber, 'title': title})
    return tracks


def parse_search_xml(text):
    """Parses the xml retrieved after entering a search query. Returns a
    list of the albums found.
    """
    doc = minidom.parseString(text)
    items = doc.getElementsByTagName('Item')
    ret = []

    for item in items:
        info = {}
        for attrib in item.getElementsByTagName('ItemAttributes'):
            if not check_binding(attrib):
                continue
            for child in attrib.childNodes:
                if child.nodeType == child.TEXT_NODE:
                    continue
                if child.tagName in XMLKEYS:
                    text_node = child.firstChild
                    if text_node.nodeType == text_node.TEXT_NODE:
                        info[XMLKEYS[child.tagName]] = text_node.data
        if not info:
            continue
        for key in IMAGEKEYS:
            image_items = item.getElementsByTagName(key)
            if image_items:
                info[IMAGEKEYS[key]] = get_image_url(image_items[0])
        info['#extrainfo'] = (translate('Amazon', '%s at Amazon.com') %
                              info.get('album', ''), get_site_url(item))
        info['#asin'] = get_asin(item)
        info['asin'] = info['#asin']
        ret.append(info)
    return ret


def retrieve_album(info, image=MEDIUMIMAGE):
    """Retrieves album from the information in info. 
    image must be either one of image_types or None. 
    If None, no image is retrieved."""
    if isinstance(info, str):
        asin = info
    else:
        asin = info['#asin']

    query_pairs = {
        "Operation": "ItemLookup",
        "Service": "AWSECommerceService",
        'ItemId': asin,
        'ResponseGroup': 'Tracks',
        'AssociateTag': 'puddletag-20'}
    url = create_aws_url(access_key, secret_key, query_pairs)

    if isinstance(info, str):
        write_log(translate('Amazon',
                            'Retrieving using ASIN: %s') % asin)
    else:
        write_log(translate('Amazon',
                            'Retrieving XML: %1 - %2').arg(
            info.get('artist', '')).arg(info.get('album', '')))
    xml = urlopen(url)

    if isinstance(info, str):
        tracks = parse_album_xml(xml)
    else:
        tracks = parse_album_xml(xml, info['album'])

    if image in image_types:
        url = info[image]
        write_log(translate("Amazon", 'Retrieving cover: %s') % url)
        info.update({'__image': retrieve_cover(url)})
    return tracks


def retrieve_cover(url):
    data = urlopen(url)
    return [{DATA: data}]


def search(artist=None, album=None):
    if artist and album:
        keywords = '+'.join([artist, album])
    elif artist:
        keywords = artist
    else:
        keywords = album
    keywords = re.sub('(\s+)', '+', keywords)
    return keyword_search(keywords)


# A couple of things you should be aware of.
# If you're retrieving urls use puddlestuff.tagsources.urlopen instead of the
# generic urllib functions. When I implement some progress bars, proxies, etc
# your tag sources will benefit automatically. Pass it your url and
# it'll return your data.

# Raise puddlestuff.tagsources.RetrievalError if an error occurs. It
# accepts a message the only argument (may be html).

# Images must be a list of  dictonaries with the
# following keys (all from puddlestuff.audioinfo):
# DATA: Required. The images string data.
# MIMETYPE: either 'image/jpg' or 'image/png'
# DESCRIPTION: the image's description
# IMAGETYPE: Index of the element corresponding to audioinfo.IMAGETYPES

# The only thing required is just a Tag Source object,
# which'll be the interface to puddletag.
class Amazon(object):
    # The name attribute is required.
    name = 'Amazon'
    # group_by specifies how the tag sources wants files to be grouped.
    # in this case they'll be grouped by album first and then by artists.

    # The values passed to Object.search will be album (a string)
    # and dictionary containing the different artists as keys and
    # a list of tags (dictionaries) as the values.
    group_by = ['album', 'artist']

    # So for these values the values passed to Object.search may be
    # ("Give Up", artist={'The Postal Service': [track listing...]})

    # Each element of track listing is a dictionary of field: value keys
    # containing file-specific info., eg.
    # {'track': ['10'], 'title': ['Natural Anthem'], '__length': '5:07'}
    # values are usually lists and "builtin" values are strings.
    # All strings are unicode, so don't worry about conversions.

    tooltip = translate('Amazon',
                        """<p>Enter search parameters here. If empty, the selected files
                        are used.</p>
                        <ul>
                        <li><b>artist;album</b>
                        searches for a specific album/artist combination.</li>
                        <li>To list the albums by an artist leave off the album part,
                        but keep the semicolon (eg. <b>Ratatat;</b>).
                        For a album only leave the artist part as in
                        <b>;Resurrection.</li>
                        <li>Entering keywords <b>without a semi-colon (;)</b> will do an
                        Amazon album search using those keywords.</li>
                        </ul>""")

    # __init__ should not accept any arguments.
    def __init__(self):
        super(Amazon, self).__init__()
        self._getcover = True
        self.covertype = 1

        # Object.preferences is a list of lists definining the the controls
        # that'll be used to created the Tag Source's config dialog.

        # Currently, there are three types of controls:
        # TEXT, COMBO and CHECKBOX. They correspond to QLineEdit,
        # QComboBox and QCheckBox respectively.

        # Each control requires three arguments in order to be created.
        # 1. Some descriptive text that's shown in a label.
        # 2. The control type, either TEXT, COMBO or CHECKBOX
        # 3. For TEXT this argument is the default text. It's not required.
        #   For COMBO, the default argument is a list containing a list
        #   of strings as the first item. 
        #   And the default index as the second item. eg.
        #   [['text1', 'text2'], 1]
        #   Checkboxes can either be checked or not so 
        #   default arguments must either True or False.

        # When the user has finished editing, the Object.applyPrefs will be
        # called with a list of values correcsponding to the order
        # in which the were defined.
        # The value returned will be either True or False for CHECKBOX.
        # For TEXT, it'll be just the text and for COMBO it'll be the index
        # the user's selected.

        # Values will be saved autotically and the applyPrefs method
        # will be called when puddletag starts.

        self.preferences = [
            [translate('Amazon', 'Retrieve Cover'), CHECKBOX, True],
            [translate('Amazon', 'Cover size to retrieve'), COMBO,
             [[translate('Amazon', 'Small'),
               translate('Amazon', 'Medium'),
               translate('Amazon', 'Large')], 1]],
            [translate('Amazon', 'Access Key (Stored '
                                 'as plain-text. Leave empty for default.)'), TEXT, ''],
            [translate('Amazon', 'Secret Key (Stored '
                                 'as plain-text. Leave empty for default.)'), TEXT, ''],
        ]

    def keyword_search(self, text):
        """Searches for albums by keywords, text."""
        # Should search for the keywords in text.
        # This method is optional, but recommended.

        # The format artist1;album1|artist2;album2 should be accepted.
        # Use the parse_searchstring method to separate text
        # into a list of artist album pairs as in:
        # [(artist1, album1), (artist2, album2)]
        try:
            params = parse_searchstring(text)
            artists = [params[0][0]]
            album = params[0][1]
        except RetrievalError:
            album = text
            artists = None
        return self.search(album, artists)

    def search(self, album, artists):
        # Required.
        # See group_by's explanation for an overview of the arguments
        # that'll be passed to this function.

        # It should return a list consisting of (albuminfo, tracklisting)
        # pairs.

        # albuminfo is a dictionary containing information applicable to
        # the whole album name like
        # {'artist': ['The Postal Service'], 'album': ['Give Up'],
        #    'year': '2003'}
        # Values can be either strings or lists of strings,
        # but all strings must be unicode!

        # Any key starting with '#' will be considered source specific and
        # will not be changed under any circumstances. Use them to store
        # any info that'll be used later to retrieve tracks.

        # Tracks use the same format as albums, but contain info specific to a
        # a track eg. [
        #    {'title': 'The District Sleeps tonight', 'track': '1'},
        #    {'title': 'Such Great Heights', '2'}
        #    .....
        #    ]

        # Return An empty list (info, []) if the tag source
        # doesn't include tracks with a lookup. Tracks can later
        # be retrieved at the user's request.

        # Do the same even if an exact match was found, but an extra
        # lookup is required to retrieve tracks.

        if artists:
            if len(artists) > 1:
                artist = 'Various Artists'
            else:
                try:
                    artist = list(artists.keys())[0]
                except AttributeError:
                    artist = artists[0]
        else:
            artist = None

        retrieved_albums = search(artist, album)
        matches = check_matches(retrieved_albums, artist, album)
        return [(info, []) for info in matches]

    def retrieve(self, info):
        # Required. Will retrieve track listing using
        # info previously obtained from Object.search.

        # Should return albuminfo (many tag sources return more info on
        # the second lookup) and tracklisting.
        if self._getcover:
            return info, retrieve_album(info, self.covertype)
        else:
            return info, retrieve_album(info, None)

    def applyPrefs(self, args):
        self._getcover = args[0]
        self.covertype = image_types[args[1]]
        global access_key
        global secret_key
        if args[2]:
            access_key = args[2]
            secret_key = args[3]
        else:
            access_key = default_access_key
            secret_key = default_secret_key


# Required in order to let your tagsource be loaded.
tagsources = [Amazon]
info = Amazon

if __name__ == '__main__':
    x = Amazon()
    print(x.keyword_search('amy winehouse'))
