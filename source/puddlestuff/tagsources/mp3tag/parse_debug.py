import codecs
import pdb

from ..mp3tag import open_script, Cursor

dbg_skip = ['ifnot', 'do', 'while']
src_skip = ['endif', 'do', 'while', 'ifnot', 'else']


def parse_group(group):
    group = group.strip().split('\n')
    ret = {}
    params = {}
    desc = ''
    prevout = False
    for i, line in enumerate(group):
        if prevout and line.strip():
            if line.strip().endswith("<"):
                ret['output'] += "\n" + line.strip()[:-1]
                prevout = False
            else:
                ret['output'] += "\n" + line.replace('\r', '')
            continue
        prevout = False
        try:
            desc, value = [z.strip() for z in line.split(':', 1)]
            desc = desc.lower()
        except ValueError:
            continue

        if desc == 'script-line':
            ret['lineno'] = int(value)
        elif desc == 'command':
            ret['cmd'] = value
        elif desc == 'output':
            ret['output'] = value[1:-1] if value.endswith("<") else value[1:]
            prevout = True
        elif desc.startswith('parameter'):
            params[desc.split()[1]] = value[1:-1]
        elif desc == 'line and position':
            ret['line'] = group[i + 1].strip()
            ret['charno'] = group[i + 2].find('^')
    if params:
        ret['params'] = [params[str(k)] for k in sorted(map(int, params))]
    return ret


def parse_total_group(group):
    fields = [_f for _f in group.split('\n output["')[1:] if _f]
    output = {}
    for field in fields:
        end_fieldname = field.find('"')
        fieldname = field[:end_fieldname].strip()
        text = field[field.find('=', end_fieldname):].strip()[1:-1]
        output[fieldname] = text
    return output


def parse_debug(text):
    delim = '-' * 60
    linenos = [i for i, z in enumerate(text.split('\n'))
               if z.strip() == delim][1:]

    groups = [z.strip() for z in text.split(delim)[3:]]
    return (list(zip(linenos, list(map(parse_group, groups[:-1])))),
            parse_total_group(groups[-1]))


def parse_file(fn):
    fo = codecs.open(fn, 'rU', 'utf16')
    text = fo.read().replace('\r\n', '\n').replace('\r', '\n')
    fo.close()
    return parse_debug(text)


def compare_retrieval(srcfn, html, debug, album=True):
    idents, search_source, album_source = open_script(srcfn)
    cursor = Cursor(html, album_source if album else search_source)
    source_parsed = cursor.parse_page(debug=True)
    debug_parsed = parse_debug(debug)[0]
    i = 0
    for cnt, dbg in debug_parsed:
        if dbg['cmd'] in dbg_skip:
            continue
        try:
            while source_parsed[i]['cmd'] in src_skip:
                del (source_parsed[i])
        except:
            pdb.set_trace()
        src = source_parsed[i]
        # print src['cmd'], src['lineno']
        src['params'] = [str(z) if not isinstance(z, str) else z for z in src['params']]
        if 'params' not in dbg and src['params'] == []:
            dbg['params'] = []
        if dbg != src:
            if dbg.get('params') != src.get('params'):
                src = src.copy()
                src['params'] = [_f for _f in src['params'] if _f]
                if dbg != src:
                    pdb.set_trace()
                    print(i, [z for z in src if src[z] != dbg[z]])
                    pdb.set_trace()
                    exit()
        i += 1


if __name__ == '__main__':
    doc_path = "~/Documents/python/puddletag-hg/source/tests"
    fn = doc_path + 'discogs_xml_all.src'
    compare_retrieval(fn, codecs.open(doc_path + "w", 'rU', 'utf8').read().replace('\r', '\n'),
                      codecs.open(doc_path + "debug.txt", 'rU', 'utf16').read(), True)
