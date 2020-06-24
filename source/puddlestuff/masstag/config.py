import glob
import os

from ..constants import CONFIGDIR
from ..masstag import (fields_from_text, MassTagProfile,
                       TagSourceProfile)
from ..puddleobjects import PuddleConfig
from ..audioinfo import encode_fn

PROFILEDIR = os.path.join(CONFIGDIR, 'masstagging')
CONFIG = os.path.join(CONFIGDIR, 'masstagging.conf')

ALBUM_BOUND = 'album_bound'
TRACK_BOUND = 'track_bound'
PATTERN = 'pattern'
FIELDS = 'fields'
JFDI = 'jfdi'
NAME = 'name'
DESC = 'desc'
EXISTING_ONLY = 'leave_existing'
REPLACE_FIELDS = 'replace_fields'


class DummyTS(object):
    group_by = []


def convert_mtps(dirpath=PROFILEDIR):
    for fn in glob.glob(PROFILEDIR + '/*.conf'):
        mtp = convert_mtp(fn)
        os.rename(fn, os.path.splitext(fn)[0] + '.old')
        save_mtp(mtp, os.path.join(dirpath, encode_fn(mtp.name)) + '.mtp')


def convert_mtp(filename):
    cparser = PuddleConfig(filename)
    info_section = 'info'
    name = cparser.get(info_section, NAME, '')
    numsources = cparser.get(info_section, 'numsources', 0)
    album_bound = cparser.get(info_section, ALBUM_BOUND, 70) / 100.0
    track_bound = cparser.get(info_section, TRACK_BOUND, 80) / 100.0
    match_fields = cparser.get(info_section, FIELDS, ['artist', 'title'])
    pattern = cparser.get(info_section, PATTERN,
                          '%artist% - %album%/%track% - %title%')
    jfdi = cparser.get(info_section, JFDI, True)
    desc = cparser.get(info_section, DESC, '')
    existing = cparser.get(info_section, EXISTING_ONLY, False)

    ts_profiles = []
    for num in range(numsources):
        section = 'config%s' % num
        get = lambda key, default: cparser.get(section, key, default)

        source = DummyTS()
        source.name = get('source', '')
        fields = fields_from_text(get('fields', ''))
        no_result = get('no_match', 0)

        ts_profiles.append(TagSourceProfile(None, source, fields,
                                            no_result))

    return MassTagProfile(name, desc, match_fields, None,
                          pattern, ts_profiles, album_bound, track_bound, jfdi, existing,
                          '')


def load_all_mtps(dirpath=PROFILEDIR, tag_sources=None):
    if tag_sources is None:
        tag_sources = {}
    mtps = [mtp_from_file(fn, tag_sources) for fn
            in glob.glob(dirpath + '/*.mtp')]
    try:
        order = open(os.path.join(dirpath, 'order'), 'r').read().split('\n')
    except EnvironmentError:
        return mtps

    order = [z.strip() for z in order]
    first = []
    last = []

    names = dict([(mtp.name, mtp) for mtp in mtps])
    mtps = [names[name] for name in order if name in names]
    mtps.extend([names[name] for name in names if name not in order])

    return mtps


def mtp_from_file(filename=CONFIG, tag_sources=None):
    if tag_sources is None:
        tag_sources = {}
    else:
        tag_sources = dict((z.name, z) for z in tag_sources)

    cparser = PuddleConfig(filename)
    info_section = 'info'

    name = cparser.get(info_section, NAME, '')
    numsources = cparser.get(info_section, 'numsources', 0)
    album_bound = cparser.get(info_section, ALBUM_BOUND, 70) / 100.0
    track_bound = cparser.get(info_section, TRACK_BOUND, 80) / 100.0
    match_fields = cparser.get(info_section, FIELDS, ['artist', 'title'])
    pattern = cparser.get(info_section, PATTERN,
                          '%artist% - %album%/%track% - %title%')
    jfdi = cparser.get(info_section, JFDI, True)
    desc = cparser.get(info_section, DESC, '')
    leave_existing = cparser.get(info_section, EXISTING_ONLY, False)
    regexps = ''

    ts_profiles = []
    for num in range(numsources):
        section = 'config%s' % num
        get = lambda key, default: cparser.get(section, key, default)

        source = tag_sources.get(get('source', ''), None)
        no_result = get('no_match', 0)
        fields = fields_from_text(get('fields', ''))
        replace_fields = fields_from_text(get('replace_fields', ''))

        ts_profiles.append(TagSourceProfile(None, source, fields,
                                            no_result, replace_fields))

    mtp = MassTagProfile(name, desc, match_fields, None,
                         pattern, ts_profiles, album_bound, track_bound, jfdi,
                         leave_existing, regexps)

    return mtp


def save_mtp(mtp, filename=CONFIG):
    cparser = PuddleConfig(filename)
    info_section = 'info'

    cparser.set(info_section, NAME, mtp.name)
    for key in ['name', 'desc', 'file_pattern', 'fields',
                'jfdi', 'leave_existing']:
        cparser.set(info_section, key, getattr(mtp, key))

    for key in ['album_bound', 'track_bound']:
        cparser.set(info_section, key, int(getattr(mtp, key) * 100))

    cparser.set(info_section, 'numsources', len(mtp.profiles))
    for num, tsp in enumerate(mtp.profiles):
        section = 'config%s' % num
        name = tsp.tag_source.name if tsp.tag_source else ''
        cparser.set(section, 'source', name)
        cparser.set(section, 'if_no_result', tsp.if_no_result)
        cparser.set(section, 'fields', ','.join(tsp.fields))
        cparser.set(section, 'replace_fields', ','.join(tsp.replace_fields))


if __name__ == '__main__':
    fns = glob.glob(PROFILEDIR + '/Local.conf')
    convert_mtps(PROFILEDIR)
