"""Record the Discogs responses tests/unit/test_discogs.py serves from a
local web server.

Each one is requested as puddletag requests it, cut down to the release data
Discogs publishes under CC0, and saved in discogs/. README.md gives the
addresses and the license. Needs network access; the tests never run it.

    venv/bin/python tests/data/record_discogs.py
"""
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / 'discogs'
SERVER = 'https://api.discogs.com/'
USER_AGENT = 'puddletag-tests (https://github.com/puddletag/puddletag)'
MASTERS = [
    96559,  # Never Gonna Give You Up
]
RELEASES = [
    249504,  # Never Gonna Give You Up, a 7" single: sides A and B
    367511,  # The Wall, two LPs: sides A1 to D7, no durations
    1257896,  # Existence Dance Festival, a compilation: track artists and credits
    10102399,  # The Beatles, two CDs: 1-1 to 2-13, then a Data track
    16106482,  # Dvořák's Legends: an index track of ten movements
]
# Restricted Data under Discogs' API Terms of Use, wherever it appears:
# images and their addresses, marketplace data, and the community's (user)
# data.
NOT_CC0 = ['blocked_from_sale', 'community', 'estimated_weight', 'images',
           'lowest_price', 'num_for_sale', 'thumb', 'thumbnail_url']
# Not read by puddletag: links to videos on other sites, with their
# descriptions.
UNREAD = ['videos']


def fetch(url):
    """The body of url, sent as puddletag sends it (gzip accepted), retried
    after a 429 (how Discogs answers too many requests); then a pause, for
    at most 25 requests a minute, Discogs' limit without a token."""
    for attempt in range(3):
        request = urllib.request.Request(
            url, headers={'Accept-Encoding': 'gzip', 'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 2:
                raise
            time.sleep(60)
            continue
        time.sleep(2.5)
        return gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data


def trim(value):
    if isinstance(value, dict):
        return {key: trim(item) for key, item in value.items()
                if key not in NOT_CC0 and key not in UNREAD}
    if isinstance(value, list):
        return [trim(item) for item in value]
    return value


def save(name, data):
    text = json.dumps(trim(json.loads(data)), ensure_ascii=False, indent=1) + '\n'
    (OUT / name).write_text(text, encoding='utf-8')
    print(f'discogs/{name}: {len(text.encode())} bytes')


def main():
    OUT.mkdir(exist_ok=True)
    for master_id in MASTERS:
        save(f'master-{master_id}.json', fetch(f'{SERVER}masters/{master_id}'))
    for release_id in RELEASES:
        save(f'release-{release_id}.json', fetch(f'{SERVER}releases/{release_id}'))


if __name__ == '__main__':
    main()
