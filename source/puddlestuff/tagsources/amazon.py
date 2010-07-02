# -*- coding: utf-8 -*-
import urllib2, urllib
import hmac
import hashlib
import base64
import time, pdb, os, re
from xml.dom import minidom
from puddlestuff.util import split_by_tag
from puddlestuff.tagsources import write_log, set_status, RetrievalError, urlopen, parse_searchstring
from puddlestuff.constants import CHECKBOX, COMBO, SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig

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

def get_text(node):
    return node.firstChild.data

def check_binding(node):
    binding = node.getElementsByTagName(u'Binding')[0].firstChild.data
    return binding == u'Audio CD'

def get_asin(node):
    return node.getElementsByTagName(u'ASIN')[0].firstChild.data

def get_image_url(node):
    return node.getElementsByTagName(u'URL')[0].firstChild.data

def page_url(node):
    return node.getElementsByTagName(u'DetailPageURL')[0].firstChild.data

def aws_url(aws_access_key_id, secret, query_dictionary):
    query_dictionary["AWSAccessKeyId"] = aws_access_key_id
    query_dictionary["Timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", 
        time.gmtime())
    #query_pairs = map(
            #lambda (k,v): (k + "=" + urllib2.quote(v)),
            #query_dictionary.items())
    items = [(key, value.encode('utf8')) for key, value in 
        query_dictionary.items()]
    query = urllib.urlencode(sorted(items))
    #query_pairs.sort()
    #query = "&".join(query_pairs)
    hm = hmac.new(secret, "GET\nwebservices.amazon.com\n/onca/xml\n" \
                    + query, hashlib.sha256)
    signature = urllib2.quote(base64.b64encode(hm.digest()))

    query = "http://webservices.amazon.com/onca/xml?%s&Signature=%s" % (
        query, signature)
    return query

def check_matches(albums, artist=None, album_name=None):
    if artist and album_name:
        album_name = album_name.lower()
        artist = artist.lower()
        return [album for album in albums if 
            album['album'].lower() == album_name and 
            album['artist'].lower() == artist]
    elif artist:
        artist = artist.lower()
        return [album for album in albums if album['artist'] == artist]
    elif album_name:
        album_name = album_name.lower()
        return [album for album in albums if album['album'] == album_name]
    else:
        return albums

def parse_album_xml(text, album=None):
    doc = minidom.parseString(text)
    album_item = doc.getElementsByTagName('Item')[0]
    tracklist = album_item.getElementsByTagName('Tracks')[0]
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
                    'album': u'%s (Disc %s)' % (album, discnum + 1)})
            else:
                tracks.append({'track': tracknumber, 'title': title})
    return tracks

def parse_xml(text):
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
        info['#extrainfo'] = ('Album at Amazon', page_url(item))
        info['#asin'] = get_asin(item)
        ret.append(info)
    return ret

def retrieve_album(info, image=MEDIUMIMAGE):
    if isinstance(info, basestring):
        asin = info
    else:
        asin = info['#asin']
    query_pairs = {
        "Operation": u"ItemLookup",
        "Service":u"AWSECommerceService",
        'ItemId': asin,
        'ResponseGroup': u'Tracks'}
    url = aws_url('AKIAJ3KBYRUYQN5PVQGA', 
        'vhzCFZHAz7Eo2cyDKwI5gKYbSvEL+RrLwsKfjvDt', query_pairs)

    if isinstance(info, basestring):
        write_log(u'Retrieving using ASIN: %s' % asin)
    else:
        write_log(u'Retrieving XML: %s - %s' % (info['artist'], info['album']))
    xml = urlopen(url)
    
    if isinstance(info, basestring):
        tracks = parse_album_xml(xml)
    else:
        tracks = parse_album_xml(xml, info['album'])

    if image in image_types:
        url = info[image]
        write_log(u'Retrieving cover: %s' % url)
        info.update({'__image': retrieve_cover(url)})
    return tracks

def retrieve_cover(url):
    data = urlopen(url)
    return [{'data': data}]

def search(artist=None, album=None):
    if artist and album:
        keywords = u' '.join([artist, album])
    elif artist:
        keywords = artist
    else:
        keywords = album
    keywords = re.sub('(\s+)', u'+', keywords)
    return keyword_search(keywords)

def keyword_search(keywords):
    write_log(u'Retrieving search results for keywords: %s' % keywords)
    query_pairs = {
            "Operation": u"ItemSearch",
            'SearchIndex': u'Music',
            "ResponseGroup":u"ItemAttributes,Images",
            "Service":u"AWSECommerceService",
            'ItemPage': u'1',
            'Keywords': keywords}
    url = aws_url('AKIAJ3KBYRUYQN5PVQGA', 
        'vhzCFZHAz7Eo2cyDKwI5gKYbSvEL+RrLwsKfjvDt', query_pairs)
    xml = urlopen(url)
    #f = open('searchxml.xml', 'w')
    #f.write(xml)
    #f.close()
    return parse_xml(xml)

class Amazon(object):
    name = 'Amazon'
    def __init__(self):

        cparser = PuddleConfig()
        cparser.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        self._getcover = cparser.get('amazon', 'retrievecovers', 
            True)
        self.covertype = image_types[cparser.get('amazon', 'covertype', 1)]

        self.preferences = [['Retrieve Cover', CHECKBOX, self._getcover],
            ['Cover size to retrieve', COMBO, 
                [['Small', 'Medium', 'Large'], 1]]]
    
    def _search(self, d):
        ret = []
        for artist, albums in d.items():
            for album in albums:
                retrieved_albums = search(artist, album)
                matches = check_matches(retrieved_albums, artist, album)
                if len(matches) == 1:
                    info = matches[0]
                    if self._getcover:
                        info, tracks = self.retrieve(info)
                    ret.append([info, tracks])
                else:
                    ret.extend([[info, []] for info in retrieved_albums])
        return ret
    
    def keyword_search(self, text):
        return self._search(parse_searchstring(text))
        
    def search(self, audios=None, params=None):
        return self._search(split_by_tag(audios))
    
    def retrieve(self, info):
        if self._getcover:
            return info, retrieve_album(info, self.covertype)
        else:
            return info, retrieve_album(info, None)
    
    def applyPrefs(self, args):
        self._getcover = args[0]
        self.covertype = image_types[args[1]]
        self.preferences[0][2] = self._getcover
        self.preferences[1][2][1] = args[1]
        cparser = PuddleConfig()
        cparser.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        cparser.set('amazon', 'retrievecovers', self._getcover)
        cparser.set('amazon', 'covertype', args[1])


#print search(u'OutKast', u'SpeakerBoxxx')
info = [Amazon, None]
name = 'Amazon'

##u'Service=AWSECommerceService&AWSAccessKeyId=AKIAJ3KBYRUYQN5PVQGA&Operation=ItemSearch&SearchIndex=Music&Keywords=Alicia&ItemPage=1&ResponseGroup=ItemAttributes,Small,Images'
##print aws_url(key, lic, query_pairs)
#print len(parse_xml(open('search.xml','r').read()))