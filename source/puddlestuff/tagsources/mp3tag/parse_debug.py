# -*- coding: utf-8 -*-
import codecs, pdb, re, sys
from puddlestuff.tagsources.mp3tag import open_script, Cursor,Mp3TagSource

dbg_skip = ['ifnot',  'do', 'while']
src_skip = ['endif', 'do', 'while', 'ifnot', 'else']

def parse_group(group):
    group = group.strip().split(u'\n')
    ret =  {}
    params = {}
    desc = u''
    prevout = False
    for i, line in enumerate(group):
        if prevout and line.strip():
            if line.strip().endswith(u"<"):
                ret['output'] += "\n" + line.strip()[:-1]
                prevout = False
            else:
                ret['output'] += "\n" + line.replace(u'\r', u'')
            continue
        prevout = False
        try:
            desc, value = [z.strip() for z in line.split(u':', 1)]
            desc = desc.lower()
        except ValueError:
            continue
        
        if desc == u'script-line':
            ret['lineno'] = int(value)
        elif desc == u'command':
            ret['cmd'] = value
        elif desc == u'output':
            ret['output'] = value[1:-1] if value.endswith(u"<") else value[1:]
            prevout = True
        elif desc.startswith(u'parameter'):
            params[desc.split()[1]] = value[1:-1]
        elif desc == u'line and position':
            ret['line'] = group[i + 1].strip()
            ret['charno'] = group[i + 2].find('^')
    if params:
        ret['params'] = [params[unicode(k)] for k in sorted(map(int, params))]
    return ret

def parse_total_group(group):
    fields = filter(None, group.split(u'\n output["')[1:])
    output = {}
    for field in fields:
        end_fieldname = field.find(u'"')
        fieldname = field[:end_fieldname].strip()
        text = field[field.find(u'=', end_fieldname):].strip()[1:-1]
        output[fieldname] = text
    return output

def parse_debug(text):
    delim = u'-' * 60
    linenos = [i for i, z in enumerate(text.split(u'\n'))
        if z.strip() == delim][1:]
    
    groups = [z.strip() for z in text.split(delim)[3:]]
    return (zip(linenos, map(parse_group, groups[:-1])),
        parse_total_group(groups[-1]))

def parse_file(fn):
    fo = codecs.open(fn, 'rU', 'utf16')
    text = fo.read().replace('\r\n', '\n').replace('\r', '\n')
    fo.close()
    return parse_debug(text)

def compare_retrieval(srcfn, html, debug, album=True):
    idents, search_source, album_source = open_script(srcfn)
    cursor = Cursor(html, album_source if album else search_source)
    source_parsed = cursor.parse_page(debug = True)
    debug_parsed = parse_debug(debug)[0]
    i = 0
    for cnt, dbg in debug_parsed:
        if dbg['cmd'] in dbg_skip:
            continue
        try:
            while source_parsed[i]['cmd'] in src_skip:
                del(source_parsed[i])
        except:
            pdb.set_trace()
        src = source_parsed[i]
        #print src['cmd'], src['lineno']
        src['params'] = [unicode(z) if not isinstance(z, unicode) else z for z in src['params']]
        if 'params' not in dbg and src['params'] == []:
            dbg['params'] = []
        if dbg != src:
            if dbg.get('params') != src.get('params'):
                src = src.copy()
                src['params'] = filter(None, src['params'])
                if dbg != src:
                    pdb.set_trace()
                    print i, [z for z in src if src[z] != dbg[z]]
                    pdb.set_trace()
                    exit()
        i += 1

if __name__ == '__main__':
    doc_path = "~/Documents/python/puddletag-hg/source/tests"
    fn = doc_path + 'discogs_xml_all.src'
    compare_retrieval(fn, codecs.open(doc_path + "w", 'rU', 'utf8').read().replace(u'\r', u'\n'),
        codecs.open(doc_path + "debug.txt", 'rU', 'utf16').read(), True)