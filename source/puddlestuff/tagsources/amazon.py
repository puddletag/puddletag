# -*- coding: utf-8 -*-
"""Python wrapper


for Amazon web APIs

This module allows you to access Amazon's web APIs,
to do things like search Amazon and get the rc programmatically.
Described here:
  http://www.amazon.com/webservices

You need a Amazon-provided license key to use these services.
Follow the link above to get one.  These functions will look in
several places (in this order) for the license key:
- the "license_key" argument of each function
- the module-level LICENSE_KEY variable (call setLicense once to set it)
- an environment variable called AMAZON_LICENSE_KEY
- a file called ".amazonkey" in the current directory
- a file called "amazonkey.txt" in the current directory
- a file called ".amazonkey" in your home directory
- a file called "amazonkey.txt" in your home directory
- a file called ".amazonkey" in the same directory as amazon.py
- a file called "amazonkey.txt" in the same directory as amazon.py

Sample usage:
>>> import amazon
>>> amazon.setLicense('...') # must get your own key!
>>> pythonBooks = amazon.searchByKeyword('Python')
>>> pythonBooks[0].ProductName
u'Learning Python (Help for Programmers)'
>>> pythonBooks[0].URL
...
>>> pythonBooks[0].OurPrice
...

Other available functions:
- browseBestSellers
- searchByASIN
- searchByUPC
- searchByAuthor
- searchByArtist
- searchByActor
- searchByDirector
- searchByManufacturer
- searchByListMania
- searchSimilar
- searchByWishlist

Other usage notes:
- Most functions can take product_line as well, see source for possible values
- All functions can take type="lite" to get less detail in results
- All functions can take page=N to get second, third, fourth page of results
- All functions can take license_key="XYZ", instead of setting it globally
- All functions can take http_proxy="http://x/y/z" which overrides your system setting
"""

__author__ = "Mark Pilgrim (f8dy@diveintomark.org)"
__version__ = "0.64.1"
__cvsversion__ = "$Revision: 1.6 $"[11:-2]
__date__ = "$Date: 2008-04-29 19:48:09 $"[7:-2]
__copyright__ = "Copyright (c) 2002 Mark Pilgrim"
__license__ = "Python"
# Powersearch and return object type fix by Joseph Reagle <geek@goatee.net>

# Locale support by Michael Josephson <mike@josephson.org>

# Modification to _contentsOf to strip trailing whitespace when loading Amazon key
# from a file submitted by Patrick Phalen.

# Support for specifying locale and associates ID as search parameters and 
# internationalisation fix for the SalesRank integer conversion by
# Christian Theune <ct@gocept.com>, gocept gmbh & co. kg

# Support for BlendedSearch contributed by Alex Choo

from xml.dom import minidom
import os, sys, getopt, cgi, urllib, string
try:
    import timeoutsocket # http://www.timo-tasi.org/python/timeoutsocket.py
    timeoutsocket.setDefaultSocketTimeout(10)
except ImportError:
    pass

LICENSE_KEY = None
ASSOCIATE = "webservices-20"
HTTP_PROXY = None
LOCALE = "us"

# don't touch the rest of these constants
class AmazonError(Exception): pass
class NoLicenseKey(Exception): pass
_amazonfile1 = ".amazonkey"
_amazonfile2 = "amazonkey.txt"
_licenseLocations = (
    (lambda key: key, 'passed to the function in license_key variable'),
    (lambda key: LICENSE_KEY, 'module-level LICENSE_KEY variable (call setLicense to set it)'),
    (lambda key: os.environ.get('AMAZON_LICENSE_KEY', None), 'an environment variable called AMAZON_LICENSE_KEY'),
    (lambda key: _contentsOf(os.getcwd(), _amazonfile1), '%s in the current directory' % _amazonfile1),
    (lambda key: _contentsOf(os.getcwd(), _amazonfile2), '%s in the current directory' % _amazonfile2),
    (lambda key: _contentsOf(os.environ.get('HOME', ''), _amazonfile1), '%s in your home directory' % _amazonfile1),
    (lambda key: _contentsOf(os.environ.get('HOME', ''), _amazonfile2), '%s in your home directory' % _amazonfile2),
    (lambda key: _contentsOf(_getScriptDir(), _amazonfile1), '%s in the amazon.py directory' % _amazonfile1),
    (lambda key: _contentsOf(_getScriptDir(), _amazonfile2), '%s in the amazon.py directory' % _amazonfile2)
    )
_supportedLocales = {
        "us" : (None, "ecs.amazonaws.com"),   
        "uk" : ("uk", "ecs.amazonaws.co.uk"),
        "de" : ("de", "ecs.amazonaws.de"),
        "jp" : ("jp", "ecs.amazonaws.jp")
    }

## administrative functions
def version():
    print """PyAmazon %(__version__)s
%(__copyright__)s
released %(__date__)s
""" % globals()

def setAssociate(associate):
    global ASSOCIATE
    ASSOCIATE=associate

def getAssociate(override=None):
    return override or ASSOCIATE

## utility functions

def _checkLocaleSupported(locale):
    if not _supportedLocales.has_key(locale):
        raise AmazonError, ("Unsupported locale. Locale must be one of: %s" %
            string.join(_supportedLocales, ", "))

def setLocale(locale):
    """set locale"""
    global LOCALE
    _checkLocaleSupported(locale)
    LOCALE = locale

def getLocale(locale=None):
    """get locale"""
    return locale or LOCALE

def setLicense(license_key):
    """set license key"""
    global LICENSE_KEY
    LICENSE_KEY = license_key

def getLicense(license_key = None):
    """get license key

    license key can come from any number of locations;
    see module docs for search order"""
    for get, location in _licenseLocations:
        rc = get(license_key)
        if rc: return rc
    raise NoLicenseKey, 'get a license key at http://www.amazon.com/webservices'

def setProxy(http_proxy):
    """set HTTP proxy"""
    global HTTP_PROXY
    HTTP_PROXY = http_proxy

def getProxy(http_proxy = None):
    """get HTTP proxy"""
    return http_proxy or HTTP_PROXY

def getProxies(http_proxy = None):
    http_proxy = getProxy(http_proxy)
    if http_proxy:
        proxies = {"http": http_proxy}
    else:
        proxies = None
    return proxies

def _contentsOf(dirname, filename):
    filename = os.path.join(dirname, filename)
    if not os.path.exists(filename): return None
    fsock = open(filename)
    contents =  fsock.read().strip()
    fsock.close()
    return contents

def _getScriptDir():
    if __name__ == '__main__':
        return os.path.abspath(os.path.dirname(sys.argv[0]))
    else:
        return os.path.abspath(os.path.dirname(sys.modules[__name__].__file__))

class Bag: pass

def unmarshal(element):
    results = []
    rc = Bag()
    largeImageElements = [e for e in element.getElementsByTagName("LargeImage") if isinstance(e, minidom.Element)]
    if largeImageElements:
        for largeImageElement in largeImageElements:
            parent = largeImageElement.parentNode
            detailUrls = [e for e in parent.getElementsByTagName("DetailPageURL") if isinstance(e, minidom.Element)]
            if len(detailUrls) == 1:
              detailUrl = detailUrls[0].firstChild.data
            else:
              detailUrl = None
            url = largeImageElement.getElementsByTagName("URL")[0].firstChild.data
            # Skip any duplicated images
            if hasattr(rc, url):
                continue
            setattr(rc, url, "")
            results.append((url, detailUrl))
    return results

def buildURL(artist, album, license_key, locale):
    _checkLocaleSupported(locale)
    url = "http://" + _supportedLocales[locale][1] + "/onca/xml?Service=AWSECommerceService"
    url += "&AWSAccessKeyId=%s" % license_key.strip()
    url += "&Operation=ItemSearch"
    url += "&SearchIndex=Music"
    if artist and len(artist):
        url += "&Artist=%s" % (urllib.quote(artist))
    if album and len(album):
        url += "&Keywords=%s" % (urllib.quote(album))
    # just return the image information
    url += "&ResponseGroup=Images,Small"
    return url


## main functions


def search(artist, album, license_key = None, http_proxy = None, locale = None, associate = None):
    """search Amazon

    You need a license key to call this function; see
    http://www.amazon.com/webservices
    to get one.  Then you can either pass it to
    this function every time, or set it globally; see the module docs for details.

    Parameters:
    Read the Amazon Associates Web Service API (http://developer.amazonwebservices.com/connect/kbcategory.jspa?categoryID=118)
    """

    license_key = getLicense(license_key)
    locale = getLocale(locale)
    associate = getAssociate(associate)
    url = buildURL(artist, album, license_key, locale)
    proxies = getProxies(http_proxy)
    u = urllib.FancyURLopener(proxies)
    usock = u.open(url)
    xmldoc = minidom.parse(usock)

    #from xml.dom.ext import PrettyPrint
    #PrettyPrint(xmldoc)

    usock.close()
    data = unmarshal(xmldoc)

    if hasattr(data, 'ErrorMsg'):
        raise AmazonError, data.ErrorMsg
    else:
        return data

def searchByKeyword(artist, album, license_key=None, http_proxy=None, locale=None, associate=None):
    return search(artist, album, license_key, http_proxy, locale, associate)
