"""Record the MusicBrainz responses tests/unit/test_musicbrainz.py serves
from a local web server.

Each one is requested as puddletag requests it, cut down to the core data
MusicBrainz releases under CC0 and to what the tests read, and saved in
musicbrainz/. README.md gives the addresses and the license. Needs network
access; the tests never run it.

    venv/bin/python tests/data/record_musicbrainz.py
"""
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.dom import minidom

OUT = Path(__file__).parent / 'musicbrainz'
SERVER = 'https://musicbrainz.org/ws/2/'
USER_AGENT = 'puddletag-tests (https://github.com/puddletag/puddletag)'
# What puddletag's retrieve_album asks for.
INC = ('recordings+artist-credits+labels+puids+isrcs+tags+ratings'
       '+artist-rels+recording-rels+release-rels+release-group-rels'
       '+url-rels+work-rels+recording-level-rels+work-level-rels')
RELEASES = [
    '33eff102-8312-4be2-b3d9-5bd9957f0158',  # Various Artists
    '6bb3793b-f991-378e-9bff-0bd3117f2298',  # Abbey Road
    '70516629-7715-41bf-97e1-b7bf11254cb8',  # two artists, " feat. "
    'f0217095-5daf-4293-8f59-6ddec7187707',  # five discs
]
# As puddletag's search_album builds it, for two results.
SEARCHES = {
    'search-abbey-road-the-beatles.xml':
        'release/?query=release:Abbey+Road%20AND%20artistname:The+Beatles&limit=2&offset=0',
    'search-arid-the-beatles.xml':
        'release/?query=arid%3Ab10bbbfc-cf9e-42e0-be17-e2c3e1d2600d&limit=2&offset=0',
}
# Not core data, which is all MusicBrainz releases under CC0: the Cover
# Art Archive's flags, and the scores of MusicBrainz's search index.
NOT_CC0 = ['annotation', 'cover-art-archive', 'genre-list', 'rating', 'tag-list',
           'user-genre-list', 'user-rating', 'user-tag-list']
NOT_CC0_ATTRIBUTES = ['ns2:score']
# Relationships puddletag doesn't read.
UNREAD = ['url', 'work']


def fetch(url):
    """The body of url, retried after a 503 (how MusicBrainz answers too
    many requests); then a pause, for at most one request a second, as
    MusicBrainz asks."""
    for attempt in range(3):
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as e:
            if e.code != 503 or attempt == 2:
                raise
            time.sleep(10)
            continue
        time.sleep(1.5)
        return data


def trim(data):
    # minidom, the parser puddletag uses, keeps the namespace prefixes
    # (ns2:score) as they are.
    doc = minidom.parseString(data)
    for name in NOT_CC0:
        for node in list(doc.getElementsByTagName(name)):
            node.parentNode.removeChild(node)
    for node in doc.getElementsByTagName('*'):
        for name in NOT_CC0_ATTRIBUTES:
            if node.hasAttribute(name):
                node.removeAttribute(name)
    for node in list(doc.getElementsByTagName('relation-list')):
        if node.getAttribute('target-type') in UNREAD:
            node.parentNode.removeChild(node)
    return doc.toxml(encoding='utf-8')


def save(name, data):
    (OUT / name).write_bytes(data)
    print(f'musicbrainz/{name}: {len(data)} bytes')


def main():
    OUT.mkdir(exist_ok=True)
    for release_id in RELEASES:
        save(f'release-{release_id}.xml', trim(fetch(f'{SERVER}release/{release_id}?inc={INC}')))
    for name, query in SEARCHES.items():
        save(name, trim(fetch(SERVER + query)))


if __name__ == '__main__':
    main()
