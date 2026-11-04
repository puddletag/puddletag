import glob
import os

from ..constants import CONFIGDIR
from ..masstag import (fields_from_text, MassTagProfile,
                       TagSourceProfile)
from ..puddleobjects import PuddleConfig

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


def load_all_mtps(dirpath=PROFILEDIR, tag_sources=None, errors=None):
    """Loads the profiles in dirpath. A file that can't be read is left out;
    if errors is a list, (file path, error) is appended to it for each."""
    if tag_sources is None:
        tag_sources = {}
    # Same.mtp, Same_0.mtp, ..., Same_10.mtp is the order Configure Profiles
    # saved profiles with one name in.
    filenames = sorted(glob.glob(dirpath + '/*.mtp'), key=lambda fn: (len(fn), fn))
    mtps = []
    for fn in filenames:
        try:
            mtps.append(mtp_from_file(fn, tag_sources))
        except (AttributeError, TypeError, ValueError) as e:
            if errors is not None:
                errors.append((fn, e))
    try:
        order = open(os.path.join(dirpath, 'order'), 'r').read().split('\n')
    except EnvironmentError:
        return mtps

    ordered = []
    for name in (z.strip() for z in order):
        for mtp in mtps:
            if mtp.name == name:
                ordered.append(mtp)
                mtps.remove(mtp)
                break

    return ordered + mtps


def mtp_from_file(filename=CONFIG, tag_sources=None):
    if tag_sources is None:
        tag_sources = {}
    else:
        tag_sources = dict((z.name, z) for z in tag_sources)

    cparser = PuddleConfig(filename)
    info_section = 'info'
    if not isinstance(cparser.data.get(info_section), dict):
        raise ValueError("it has no info section")

    name = cparser.get(info_section, NAME, '')
    numsources = cparser.get(info_section, 'numsources', 0)
    album_bound = cparser.get(info_section, ALBUM_BOUND, 70) / 100.0
    track_bound = cparser.get(info_section, TRACK_BOUND, 80) / 100.0
    match_fields = cparser.get(info_section, FIELDS, ['artist', 'title'])
    if not isinstance(match_fields, list):
        raise ValueError("the fields to match aren't a list")
    pattern = cparser.get(info_section, 'file_pattern',
                          cparser.get(info_section, PATTERN,
                                      '%artist% - %album%/%track% - %title%'))
    jfdi = cparser.get(info_section, JFDI, False)
    desc = cparser.get(info_section, DESC, '')
    leave_existing = cparser.get(info_section, EXISTING_ONLY, False)
    regexps = ''

    ts_profiles = []
    for num in range(numsources):
        section = 'config%s' % num
        get = lambda key, default: cparser.get(section, key, default)

        source_name = get('source', '')
        source = tag_sources.get(source_name, None)
        no_result = get('if_no_result', get('no_match', 0))
        fields = fields_from_text(get('fields', ''))
        replace_fields = fields_from_text(get('replace_fields', ''))

        ts_profile = TagSourceProfile(None, source, fields,
                                      no_result, replace_fields)
        if source is None:
            ts_profile.missing_source = source_name
        ts_profiles.append(ts_profile)

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
        cparser.set(info_section, key, round(getattr(mtp, key) * 100))

    cparser.set(info_section, 'numsources', len(mtp.profiles))
    for num, tsp in enumerate(mtp.profiles):
        section = 'config%s' % num
        name = tsp.tag_source.name if tsp.tag_source else (tsp.missing_source or '')
        cparser.set(section, 'source', name)
        cparser.set(section, 'if_no_result', tsp.if_no_result)
        cparser.set(section, 'fields', ','.join(tsp.fields))
        cparser.set(section, 'replace_fields', ','.join(tsp.replace_fields))
