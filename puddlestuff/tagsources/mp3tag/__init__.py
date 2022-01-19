import codecs
import os
import re
import traceback
from copy import deepcopy
from html.entities import name2codepoint as n2cp

from pyparsing import (nums, printables, Combine, Optional,
                       QuotedString, Word, ZeroOrMore)

from .funcs import FUNCTIONS
from .. import (urlopen, get_encoding,
                write_log, retrieve_cover, set_status)
from ...audioinfo.util import CaselessDict
from ...constants import CHECKBOX
from ...functions import format_value
from ...translations import translate
from ...util import convert_dict as _convert_dict


class ParseError(Exception): pass


def unquote(s, loc, tok):
    """Doing this manually, because QuotedString's method removes \'s from
    regular expressions."""
    tok = tok.pop()[1:-1]
    return tok.replace('\\"', '"')


def getnum(s, l, t):
    return int(''.join(t))


STRING = QuotedString('"', '\\', unquoteResults=False).setParseAction(unquote)
NUMBER = Combine(Optional('-') + Word(nums)).setParseAction(getnum)
COVER = '#cover-url'

ARGUMENT = STRING | NUMBER
ARGUMENT.ignore('#' + ZeroOrMore(Word(printables)))

MTAG_KEYS = {
    '_length': '__length',
    '_url': '#url',
    'coverurl': COVER,
    'publisher': 'label',
    'track temp': 'track'}


def convert_entities(s):
    s = re.sub('&#(\d+);', lambda m: chr(int(m.groups(0)[0])), s)
    return re.sub('&(\w)+;',
                  lambda m: n2cp.get(m.groups(0), '&%s;' % m.groups(0)[0]), s)


def convert_value(value):
    value = [_f for _f in (z.strip() for z in value.split('|')) if _f]
    value = [convert_entities(v.replace('\\r\\n', '\n')) for v in value]
    if len(value) == 1:
        return value[0]
    return value


def convert_dict(d, keys=MTAG_KEYS):
    d = dict((i, z) for i, z in ((k.lower(), convert_value(v)) for
                                 k, v in d.items()) if z)
    return _convert_dict(d, keys)


def find_idents(lines):
    ident_lines = {}
    idents = {}
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('['):
            name, value = parse_ident(line)
            idents[name.lower()] = value
            ident_lines[i] = name.lower()
        elif not line or line.startswith('#'):
            continue

    values = sorted(ident_lines)
    max_val = max(values)
    for i, (lineno, ident) in enumerate(sorted(ident_lines.items())):
        if ident == 'parserscriptindex':
            if lineno < max_val:
                search_source = (lineno, lines[lineno + 1: values[i + 1]])
            else:
                search_source = (lineno, lines[lineno + 1:])
        elif ident == 'parserscriptalbum':
            if lineno < max_val:
                album_source = (lineno, lines[lineno + 1: values[i + 1]])
            else:
                album_source = (lineno, lines[lineno + 1:])

    try:
        offset = search_source[0]

        # Adding 2 to offset, because it's needed. I'm to lazy to go search for
        # why it is so.
        search_source = [(offset + i + 2, s) for i, s in
                         enumerate(search_source[1])]
    except UnboundLocalError:
        search_source = None

    offset = album_source[0]
    album_source = [(offset + i + 2, s) for i, s
                    in enumerate(album_source[1])]

    parser = lambda arg: parse_func(*arg)
    if search_source is not None:
        search_source = [_f for _f in map(parser, search_source) if _f]
    return (idents, search_source,
            [_f for _f in map(parser, album_source) if _f])


def open_script(filename):
    f = codecs.open(filename, 'r', encoding='utf8')
    idents, search, album = find_idents(f.readlines())
    return idents, search, album


def parse_album_page(page, album_source, url=None):
    cursor = Cursor(page, album_source)
    if url:
        cursor.output = CaselessDict({'CurrentUrl': url})
        cursor.album = CaselessDict({'CurrentUrl': url})

    cursor.parse_page()
    info = convert_dict(cursor.album)
    if hasattr(cursor.tracks, 'items'):
        tracks = []
        for field, values in cursor.tracks.items():
            values = convert_value(values)
            if tracks:
                for d, v in zip(tracks, values):
                    d[field] = v
            else:
                tracks = [{field: v} for v in values]
    else:
        tracks = [_f for _f in map(convert_dict, cursor.tracks) if _f]
    return (info, tracks)


def parse_func(lineno, line):
    line = line.strip()
    if not line:
        return

    funcname = line.split(None, 1)[0].strip()
    arg_string = line[len(funcname):]
    args = (z[0]
            for z in ARGUMENT.searchString(arg_string).asList())
    args = [i.replace('\\\\', '\\') if isinstance(i, str) else i
            for i in args]
    if funcname and not funcname.startswith('#'):
        return funcname.lower(), lineno, args


def parse_ident(line):
    ident, value = re.search('^\[(\w+)\]=(.*)$', line).groups()
    return ident, value


def parse_lines(lines):
    for line in lines:
        if line.startswith('['):
            print(parse_ident(line))
        else:
            print(parse_func(line))


def parse_search_page(indexformat, page, search_source, url=None):
    fields = [z[1:-1] for z in indexformat.split('|')]
    cursor = Cursor(page, search_source)
    if url:
        cursor.output = {'CurrentUrl': url}
    cursor.parse_page()

    i = 0
    values = cursor.cache.split('\n')
    albums = []
    exit_loop = False
    max_i = len(values) - 1
    for cached in values:
        values = [z.strip() for z in cached.split('|')]
        album = dict(list(zip(fields, values)))
        albums.append(album)
    return [_f for _f in map(convert_dict, albums) if _f]


class Cursor(object):
    def __init__(self, text, source_lines):
        self.text = text
        self.all_lines = [z + ' ' for z in text.split('\n')] + [' ']
        self.all_lowered = [z.lower() for z in self.all_lines]
        self.lineno = 0
        self.charno = 0
        self.cache = ''
        self.source = source_lines
        self.debug = False
        self._field = ''
        self.tracks = []
        self.album = CaselessDict()
        self.num_loop = 0
        self.output = self.album
        self.stop = False
        self.track_fields = set(['track'])

    def _get_char(self):
        return self.line[self.charno]

    char = property(_get_char)

    def _get_debug_file(self):
        return self._debug_file

    def _set_debug_file(self, filename):
        if not filename:
            self._debug_file = None
            return
        f = open(filename, 'w')
        self._debug_file = f

    debug_file = property(_get_debug_file, _set_debug_file)

    def _get_field(self):
        return self._field

    def _set_field(self, value):
        self.output[self._field] = self.cache
        self.cache = self.output.get(value, '')
        self._field = value

    field = property(_get_field, _set_field)

    def _get_lineno(self):
        return self._lineno

    def _set_lineno(self, value):
        self._lineno = value
        try:
            self.line = self.all_lines[self.lineno].strip()
        except IndexError:
            self.stop = True

    lineno = property(_get_lineno, _set_lineno)

    def _get_lines(self):
        return self.all_lines[self.lineno:]

    lines = property(_get_lines)

    def _get_lowered(self):
        return self.all_lowered[self.lineno:]

    lowered = property(_get_lowered)

    def log(self, text):
        if self.debug and self.debug_file:
            self._debug_file.write(('\n' + text))
            self._debug_file.flush()
        elif self.debug:
            print(text)

    def parse_page(self, debug=False):
        self.next_cmd = 0
        self.cmd_index = 0
        i = 1

        ret = []
        debug_info = []

        i = 0
        while (not self.stop) and (self.next_cmd < len(self.source)):

            self.log(str(self.output))
            cmd, lineno, args = self.source[self.cmd_index]

            self.log(str(self.source[self.cmd_index]))

            # if lineno == 106 or lineno == 108:
            # pdb.set_trace()
            # i += 1
            # print cmd, lineno, args

            # if lineno >= 436:
            # print self.cache
            # pdb.set_trace()

            if not FUNCTIONS[cmd](self, *args):
                self.next_cmd += 1

            if debug:
                debug_info.append(
                    {'lineno': lineno, 'cmd': cmd, 'params': args,
                     'output': self.cache, 'charno': self.charno,
                     'line': self.line})
            self.cmd_index = self.next_cmd

        self.output[self.field] = self.cache

        if self.output is not self.album:
            try:
                self.tracks.append(self.output)
            except AttributeError:
                self.tracks.update(self.output)
        self.stop = False

        if debug:
            return debug_info


class Mp3TagSource(object):
    def __init__(self, idents, search_source, album_source):

        self._get_cover = True
        self.preferences = [
            ['Retrieve Covers', CHECKBOX, self._get_cover]]

        self.search_source = search_source
        self.album_source = album_source
        self._search_base = idents['indexurl'] if search_source else ''
        self._separator = idents.get('wordseperator', '+')
        self.searchby = idents.get('searchby', '')
        self.group_by = ['album' if '$' in idents['searchby'] \
                             else idents['searchby'][1:-1], None]
        self.name = idents['name'] + ' [M]'
        self.indexformat = idents['indexformat'] if search_source else ''
        self.album_url = idents.get('albumurl', '')
        self.tooltip = tooltip = """<p>Enter search keywords here. If empty,
        the selected files are used.<br /><br />
        Searches are done by <b>%s</b></p>""" % self.group_by[0]

        self.html = None

    def applyPrefs(self, args):
        self._get_cover = args[0]

    def keyword_search(self, text):
        return self.search(text)

    def search(self, artist, files=None):
        if files is not None and self.searchby:
            keywords = format_value(files[0], self.searchby)
        else:
            keywords = artist
        keywords = re.sub('\s+', self._separator, keywords)

        if self.search_source is None:
            album = self.retrieve(keywords)
            return [album] if album else []

        url = self._search_base.replace('%s', keywords)

        write_log(translate('Mp3tag', 'Retrieving search page: %s') % url)
        set_status(translate('Mp3tag', 'Retrieving search page...'))
        if self.html is None:
            page = get_encoding(urlopen(url), True, 'utf8')[1]
        else:
            page = get_encoding(self.html, True, 'utf8')[1]

        write_log(translate('Mp3tag', 'Parsing search page.'))
        set_status(translate('Mp3tag', 'Parsing search page...'))
        infos = parse_search_page(self.indexformat, page, self.search_source, url)
        return [(info, []) for info in infos]

    def retrieve(self, info):
        if isinstance(info, str):
            text = info.replace(' ', self._separator)
            info = {}
        else:
            info = deepcopy(info)
            text = info['#url']

        try:
            url = self.album_url % text
        except TypeError:
            url = self.album_url + text

        info['#url'] = url

        try:
            write_log(translate('Mp3tag', 'Retrieving album page: %s') % url)
            set_status(translate('Mp3tag', 'Retrieving album page...'))
            page = get_encoding(urlopen(url), True, 'utf8')[1]
        except:
            page = ''

        write_log(translate('Mp3tag', 'Parsing album page.'))
        set_status(translate('Mp3tag', 'Parsing album page...'))
        new_info, tracks = parse_album_page(page, self.album_source, url)
        info.update(dict((k, v) for k, v in new_info.items() if v))

        if self._get_cover and COVER in info:
            cover_url = new_info[COVER]
            if isinstance(cover_url, str):
                info.update(retrieve_cover(cover_url))
            else:
                info.update(list(map(retrieve_cover, cover_url)))
        if not tracks:
            tracks = None
        return info, tracks


def load_mp3tag_sources(dirpath='.'):
    "Loads Mp3tag tag sources from dirpath and return the tag source classes."
    import glob
    files = glob.glob(os.path.join(dirpath, '*.src'))
    classes = []
    for f in files:
        try:
            idents, search, album = open_script(f)
            classes.append(Mp3TagSource(idents, search, album))
        except:
            # print translate("WebDB", "Couldn't load Mp3tag Tag Source %s") % f
            traceback.print_exc()
            continue
    return classes


from ..discogs import urlopen

if __name__ == '__main__':
    # text = open(sys.argv[1], 'r').read()
    # text = open(sys.argv[1], 'r').read()
    tagsources = load_mp3tag_sources('.')
    albums = tagsources[2].search('Goth-Erotika')
    tagsources[2]._get_cover = False
    print(tagsources[2].retrieve(albums[0][0]))
    # pdb.set_trace()
    # import puddlestuff.tagsources
    # encoding, text = puddlestuff.tagsources.get_encoding(text, True, 'utf8')

    ##pdb.set_trace()
    # idents, search, album = open_script(sys.argv[2])
    # value = parse_search_page(idents['indexformat'], text, search)

    ##value = parse_album_page(text, album, 'url')
    # print value
    # pdb.set_trace()
    # print convert_value(value)
    ##source = find_idents(lines)[1]

    ##print parse_search(idents['indexformat'], search, text)
    ###text = open('d_album.htm', 'r').read()
    ##c = Cursor(text.decode('utf8', 'replace'), source)
    ##c.parse_page()
    ###print c.cache
    ###print c.tracks[0]
    ##print '\n'.join('%s: %s' % z for z in c.album.items())
