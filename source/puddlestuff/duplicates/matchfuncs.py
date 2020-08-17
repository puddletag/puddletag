try:
    from Levenshtein import ratio, jaro, jaro_winkler


    def _ratio(a, b):
        """Ratio
    
The ratio by which the strings differ."""
        return ratio(a, b)


    def _jaro(a, b):
        """Jaro

The Jaro string similarity metric is intended for short strings like personal last names."""
        return jaro(a, b)


    def _jaro_winkler(a, b):
        """Jaro-Winkler
        
The Jaro-Winkler string similarity metric is a modification of Jaro metric giving more weight to common prefix, as spelling mistakes are more likely to occur near ends of words."""
        return a, b


    funcs = [_ratio, _jaro, _jaro_winkler]
except ImportError:
    from difflib import SequenceMatcher


    def _ratio(a, b):
        """Ratio
    
The ratio by which the strings differ."""
        return SequenceMatcher(None, a, b).ratio()


    funcs = [_ratio]


def exact(a, b):
    """Exact

Matches exactly."""
    if a == b:
        return 1
    else:
        return 0


funcs.append(exact)


def funcinfo(func):
    return (func.__doc__.split('\n')[0], '\n'.join(func.__doc__.split('\n')[2:]))


class Algo(object):
    def __init__(self, tags=None, threshold=0.85, func=_ratio, matchcase=True):
        self.threshold = threshold
        if tags is None:
            self.tags = []
        else:
            self.tags = tags
        self.func = func
        self.matchcase = matchcase

    def _setFunc(self, func):
        if isinstance(func, str):
            funcnames = [f.__name__ for f in funcs]
            try:
                func = funcs[funcnames.index(func)]
            except IndexError:
                return
        self._func = func
        self.funcname, self.funcdesc = funcinfo(func)

    def _getFunc(self):
        return self._func

    func = property(_getFunc, _setFunc)

    def pprint(self):
        threshold = '%.2f' % (self.threshold * 100) + '%'
        funcname = self.funcname
        tags = ' | '.join(self.tags)
        matchcase = ''
        if self.matchcase:
            matchcase = ' - Match Case'
        return 'Tags: ' + tags + ' - Algorithm: ' + funcname + ' - Threshold: ' + threshold + matchcase
