from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys, pdb

def dupes(tracks, tags, func, matchcase = False, threshold = 1, prevdupe = None):
    if matchcase:
        strings = [[(i, t[tag] if tag in t else u'') for i, t in enumerate(tracks)] for tag in tags]
    else:
        strings = [[(i, t[tag].lower() if tag in t else u'') for i, t in enumerate(tracks)] for tag in tags]
    if prevdupe:
        ret = prevdupe
        start = 0
    else:
        start = 1
        ret = finddupes(strings[0], func, threshold)

    for s in strings[start:]:
        l = []
        dups = finddupes(s, func, threshold)
        if len(dups) > len(ret):
            for z in dups:
                x = [z.intersection(r) for r in ret if z.intersection(r)]
                if x:
                    l.append(x[0])
        else:
            for z in ret:
                x = [z.intersection(r) for r in dups if z.intersection(r)]
                if x:
                    l.append(x[0])            
        ret = l
    return ret

def delete(l, dellist):
    while dellist:
        del(l[dellist[0]])
        dellist = [z - 1 for z in dellist][1:]

def finddupes(strings, func, threshold = 1):
    dupes = []
    while strings:
        index, mainstring = strings[0]
        dupeset = set([index])
        li = strings[1:]
        todelete = []
        for z, s in enumerate(li):
            if func(s[1], mainstring) >= threshold:
                dupeset.add(s[0])
                todelete.append(z + 1)
        delete(strings, todelete)
        strings = strings[1:]
        if len(dupeset) > 1:
            dupes.append(dupeset)
    return dupes

def dupesinlib(library, algs, maintag = None, artists = None):
    alg = algs[0]
    func = alg.func
    percent = alg.threshold
    tags = alg.tags

    if not maintag:
        maintag = alg.tags[0]
    if not artists:
        artists = library.distinctValues(maintag)
    yield artists
    for a in artists:
        tracks = library.tracksByTag(maintag, a)
        st = [z.stringtags() for z in library.tracksByTag(maintag, a)]
        ret = dupes(st, tags, alg.func, alg.matchcase, alg.threshold)
        for alg in algs:
            ret = dupes(st, alg.tags, alg.func, alg.matchcase, alg.threshold, ret)
        yield [[tracks[i]  for i in z] for z in ret]

if __name__ == '__main__':
    import prokyon
    lib = prokyon.Prokyon('tracks', user='prokyon', passwd='prokyon', db='prokyon')
    from Levenshtein import ratio

    algos = [algo(['artist', 'title'], 0.80, ratio), algo(['artist', 'title'], 0.70, ratio)]
    for z in dupesinlib(lib, algos):
        if z:
            print z