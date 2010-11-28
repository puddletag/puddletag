# -*- coding: utf-8 -*-
#Example tutorial for writing a tag source plugin using Amazon's webservice API.

#The important stuff is at the bottom in the Amazon class.
#Comments (or you've created a tag source you'd like
#to share) can be directed at concentricpuddle@gmail.com

#Imports and constants.
#-----------------------------------------------------------
import base64, hmac, hashlib, os, re, time, urllib2, urllib

from xml.dom import minidom

from puddlestuff.constants import CHECKBOX, COMBO, SAVEDIR
from puddlestuff.tagsources import (write_log, set_status, RetrievalError,
    urlopen, parse_searchstring)
from puddlestuff.audioinfo import DATA
import urllib2, gzip, cStringIO, pdb, socket
from copy import deepcopy

search_url = 'http://www.discogs.com/search?type=releases&q=%s&f=xml&api_key=c6e33897b6'
album_url = 'http://www.discogs.com/release/%s?f=xml&api_key=c6e33897b6'

SMALLIMAGE = '#smallimage'
LARGEIMAGE = '#largeimage'

image_types = [SMALLIMAGE, LARGEIMAGE]

ALBUM_KEYS = {
    'title': 'album',
    'uri': 'discogs_uri',
    'summary': 'discogs_summary',
    'released': 'year'}

TRACK_KEYS = {
    'position': 'track',
    'duration': '__length',}

def convert_dict(d, keys=TRACK_KEYS):
    d = deepcopy(d)
    for key in keys:
        if key in d:
            d[keys[key]] = d[key]
            del(d[key])
    return d

IMAGEKEYS = {
    'SmallImage': SMALLIMAGE,
    'LargeImage': LARGEIMAGE}

def is_release(element):
    return element.attributes['type'].value == 'release'

def node_to_dict(node):
    ret = {}
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            continue
        text_node = child.firstChild
        if text_node is None:
            continue
        if text_node.nodeType == text_node.TEXT_NODE:
            ret[child.tagName] = text_node.data
    return ret

def get_text(node):
    """Returns the textual data in a node."""
    try:
        return node.firstChild.data
    except AttributeError:
        return

def check_binding(node):
    """Checks whether a returned item as an Audio CD."""
    binding = node.getElementsByTagName(u'Binding')[0].firstChild.data
    return binding == u'Audio CD'

def get_asin(node):
    """Retrieves the ASIN of a node."""
    return node.getElementsByTagName(u'ASIN')[0].firstChild.data

def get_image_url(node):
    return node.getElementsByTagName(u'URL')[0].firstChild.data

def page_url(node):
    return node.getElementsByTagName(u'DetailPageURL')[0].firstChild.data

def aws_url(aws_access_key_id, secret, query_dictionary):
    """Creates the query url that'll be used to query Amazon's service."""
    query_dictionary["AWSAccessKeyId"] = aws_access_key_id
    query_dictionary["Timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
        time.gmtime())

    items = [(key, value.encode('utf8')) for key, value in
        query_dictionary.items()]
    query = urllib.urlencode(sorted(items))

    hm = hmac.new(secret, "GET\nwebservices.amazon.com\n/onca/xml\n" \
        + query, hashlib.sha256)
    signature = urllib2.quote(base64.b64encode(hm.digest()))

    query = "http://webservices.amazon.com/onca/xml?%s&Signature=%s" % (
        query, signature)
    return query

def check_matches(albums, artist=None, album_name=None):
    """Returns any album in albums with the same matching artist and
    album_name's. If no matches are found, original list is returned."""
    ret = []
    if artist and album_name:
        album_name = album_name.lower()
        artist = artist.lower()

        ret = [album for album in albums if
            album['album'].lower() == album_name and
            album['artist'].lower() == artist]
    elif artist:
        artist = artist.lower()
        ret = [album for album in albums if album['artist'] == artist]
    elif album_name:
        album_name = album_name.lower()
        ret = [album for album in albums if album['album'] == album_name]

    return ret if ret else albums

def keyword_search(keywords):
    write_log(u'Retrieving search results for keywords: %s' % keywords)
    url = search_url % urllib.quote_plus(keywords)
    #text = open('results.xml', 'r').read()
    text = urlopen(url)
    page = open('results.xml', 'w')
    page.write(text)
    page.close()
    return parse_search_xml(text)

def parse_album_xml(text):
    """Parses the retrieved xml for an album and get's the track listing."""
    doc = minidom.parseString(text)
    info = {}
    info['artist'] = [node_to_dict(e)['name'] for e in
        doc.getElementsByTagName('artists')[0].childNodes if node_to_dict(e)]

    labels = doc.getElementsByTagName('labels')
    if labels:
        for label in labels[0].childNodes:
            try:
                info['label'] = label.attributes['name'].value
                info['discogs_catno'] = label.attributes['catno'].value
            except (AttributeError, KeyError):
                continue

    formats = doc.getElementsByTagName('formats')
    if formats:
        for format in formats[0].childNodes:
            try:
                info['discogs_format'] = format.attributes['name'].value
                info['discs'] = format.attributes['qty'].value
                info['discogs_format_desc'] = filter(None,
                    [get_text(z) for z in format.childNodes[0].childNodes])
            except (AttributeError, KeyError):
                continue

    extras = doc.getElementsByTagName('extraartists')
    if extras:
        ex_artists = [node_to_dict(z) for z  in extras[0].childNodes]
        info['involvedpeople'] = u';'.join(u'%s:%s' % (e['name'], e['role'])
            for e in ex_artists)

    info['genre'] = filter(None,
        [get_text(z) for z in doc.getElementsByTagName('genres')[0].childNodes])
    info['style'] = filter(None,
        [get_text(z) for z in doc.getElementsByTagName('styles')[0].childNodes])

    text_keys = ['notes', 'country', 'released', 'title']

    for key in text_keys:
        try:
            info[key] = get_text(doc.getElementsByTagName(key)[0])
        except IndexError:
            continue

    images = doc.getElementsByTagName('images')
    if images:
        image_list = []
        for image in images[0].childNodes:
            d = dict(image.attributes.items())
            if not d:
                continue
            if d['type'] == 'primary':
                image_list.insert(0, (d['uri'], d['uri150']))
            else:
                image_list.append(0, (d['uri'], d['uri150']))
        info['#cover-url'] = image_list

    tracklist = doc.getElementsByTagName('tracklist')[0]
    return convert_dict(info, ALBUM_KEYS), filter(None,
        [convert_dict(node_to_dict(z)) for z in tracklist.childNodes])

def parse_search_xml(text):
    """Parses the xml retrieved after entering a search query. Returns a
    list of the albums found.
    """
    doc = minidom.parseString(text)
    exact = doc.getElementsByTagName('exactresults')
    results = []
    if exact:
        results = filter(is_release, exact[0].getElementsByTagName('result'))

    if not results:
        search_results = doc.getElementsByTagName('searchresults')
        results = filter(is_release, search_results[0].getElementsByTagName('result'))

    ret = []

    for result in results:
        info = node_to_dict(result)
        info['#r_id'] = re.search('\d+$', info['uri']).group()
        info['discogs_rid'] = info['#r_id']
        info = convert_dict(info, ALBUM_KEYS)
        ret.append(info)
    return ret

def retrieve_album(info, image=LARGEIMAGE):
    """Retrieves album from the information in info.
    image must be either one of image_types or None.
    If None, no image is retrieved."""
    if isinstance(info, (int, long)):
        r_id = unicode(info)
        info = {}
    elif isinstance(info, basestring):
        r_id = info
        info = {}
    else:
        r_id = info['#r_id']

    if isinstance(info, basestring):
        write_log(u'Retrieving using Release ID: %s' % r_id)
    else:
        write_log(u'Retrieving album %s' % (info['album']))
    
    xml = urlopen(album_url % r_id)
    #f = open('album.xml', 'w')
    #f.write(xml)
    #f.close()
    #xml = open('.album.xml', 'r').read()

    ret = parse_album_xml(xml)

    info = deepcopy(info)
    info.update(ret[0])

    if image in image_types and '#cover-url' in info:
        data = []
        for large, small in info['#cover-url']:
            if image == LARGEIMAGE:
                write_log(u'Retrieving cover: %s' % large)
                data.append({DATA: urlopen(large)})
            else:
                write_log(u'Retrieving cover: %s' % small)
                data.append({DATA: urlopen(small)})
        info.update({'__image': data})
    return info, ret[1]

def search(artist=None, album=None):
    if artist and album:
        keywords = u' '.join([artist, album])
    elif artist:
        keywords = artist
    else:
        keywords = album
    return keyword_search(keywords)

def urlopen(url):
    request = urllib2.Request(url)
    request.add_header('Accept-Encoding', 'gzip')
    try:
        data = urllib2.urlopen(request).read()
    except urllib2.URLError, e:
        msg = u'%s (%s)' % (e.reason.strerror, e.reason.errno)
        raise RetrievalError(msg)
    except socket.error:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)
    except EnvironmentError, e:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)

    try:
        return gzip.GzipFile(fileobj = cStringIO.StringIO(data)).read()
    except IOError:
        return data

#A couple of things you should be aware of.
#If you're retrieving urls use puddlestuff.tagsources.urlopen instead of the
#generic urllib functions. When I implement some progress bars, proxies, etc
#your tag sources will benefit automatically. Pass it your url and
#it'll return your data.

#Raise puddlestuff.tagsources.RetrievalError if an error occurs. It
#accepts a message the only argument (may be html).

#Images must be a list of  dictonaries with the
#following keys (all from puddlestuff.audioinfo):
#DATA: Required. The images string data.
#MIMETYPE: either 'image/jpg' or 'image/png'
#DESCRIPTION: the image's description
#IMAGETYPE: Index of the element corresponding to audioinfo.IMAGETYPES

#The only thing required is just a Tag Source object, which'll be the interface
#to puddletag.
class Discogs(object):
    #The name attribute is required.
    name = 'Discogs.com'
    #group_by specifies how the tag sources wants files to be grouped.
    #in this case they'll be grouped by album first and then by artists.

    #The values passed to Object.search will be album (a string)
    #and dictionary containing the different artists as keys and
    #a list of tags (dictionaries) as the values.
    group_by = [u'album', u'artist']

    #So for these values the values passed to Object.search may be
    #(u"Give Up", artist={u'The Postal Service': [track listing...]})

    #Each element of track listing is a dictionary of field: value keys
    #containing file-specific info., eg.
    # {'track': [u'10'], 'title': [u'Natural Anthem'], '__length': u'5:07'}
    # values are usually lists and "builtin" values are strings.
    #All strings are unicode, so don't worry about conversions.

    #__init__ should not accept any arguments.
    def __init__(self):
        super(Discogs, self).__init__()
        self._getcover = True
        self.covertype = 1

        #Object.preferences is a list of lists definining the the controls
        #that'll be used to created the Tag Source's config dialog.

        #Currently, there are three types of controls: TEXT, COMBO and CHECKBOX
        #which correspond to a QLineEdit, QComboBox and QCheckBox respectively.

        #Each control requires three arguments in order to be created.
        #1. Some descriptive text that's shown in a label.
        #2. The control type, either TEXT, COMBO or CHECKBOX
        #3. For TEXT this argument is the default text. It's not required.
        #   For COMBO, the default argument is a list containing a list
        #   of strings as the first item.
        #   And the default index as the second item. eg. [['text1', 'text2'], 1]
        #   Checkboxes can either be checked or not so
        #   default arguments must either True or False.

        #When the user has finished editing, the Object.applyPrefs will be
        #called with a list of values correcsponding to the order
        #in which the were defined.
        #The value returned will be either True or False for CHECKBOX.
        #For TEXT, it'll be just the text and for COMBO it'll be the index
        #the user's selected.

        self.preferences = [
            ['Retrieve Cover', CHECKBOX, True],
            ['Cover size to retrieve', COMBO,
                [['Small', 'Large'], 1]]
            ]

    def keyword_search(self, text):
        """Searches for albums by keywords, text."""
        #Should search for the keywords in text.
        #This method is optional, but recommended.

        #The format artist1;album1|artist2;album2 should be accepted.
        #Use the parse_searchstring method to separate text
        #into a list of artist album pairs as in:
        # [(artist1, album1), (artist2, album2)]
        params = parse_searchstring(text)
        artists = [params[0][0]]
        album = params[0][1]

        return self.search(album, artists)

    def search(self, album, artists):
        #Required.
        #See group_by's explanation for an overview of the arguments
        #that'll be passed to this function.

        #It should return a list consisting of (albuminfo, tracklisting) pairs.
        #albuminfo is a dictionary containing information applicable to
        #the whole album name like
        #{'artist': [u'The Postal Service'], 'album': [u'Give Up'],
        #    'year': u'2003'}
        #Values can be either strings or lists, but all strings must be
        #unicode!

        #Any key starting with '#' will be considered source specific and
        #will not be changed under any circumstances. Use them to store
        #any info that'll be used later to retrieve tracks.

        #Tracks use the same format as albums, but contain info specific to a
        #a track eg. [
        #    {'title': u'The District Sleeps tonight', 'track': u'1'},
        #    {'title': u'Such Great Heights', u'2'}
        #    .....
        #    ]

        #Return An empty list (info, []) if the tag source
        #doesn't include tracks with a lookup. Tracks can later
        #be retrieved at the user's request.

        #Do the same even if an exact match was found, but an extra
        #lookup is required to retrieve tracks.

        if len(artists) > 1:
            artist = u'Various Artists'
        else:
            artist = [z for z in artists][0]

        retrieved_albums = search(artist, album)
        matches = check_matches(retrieved_albums, artist, album)
        return [(info, []) for info in matches]

    def retrieve(self, info):
        #Required. Will retrieve track listing using
        #info previously obtained from Object.search.

        #Should return albuminfo (many tag sources return more info on
        #the second lookup) and tracklisting.
        if self._getcover:
            return retrieve_album(info, self.covertype)
        else:
            return retrieve_album(info, None)

    def applyPrefs(self, args):
        self._getcover = args[0]
        self.covertype = image_types[args[1]]

info = Discogs

if __name__ == '__main__':
    print parse_album_xml(open('album.xml', 'r').read())

#print keyword_search('Minutes to midnight')