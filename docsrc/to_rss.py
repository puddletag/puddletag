    # -*- coding: utf-8 -*-
import sys

from htmllib import HTMLParser
import formatter, re
from htmlentitydefs import name2codepoint as n2cp

def convert_entities(s):
    s = re.sub('&#(\d+);', lambda m: unichr(int(m.groups(0)[0])), s)
    return re.sub('&(\w)+;',
        lambda m: n2cp.get(m.groups(0), u'&%s;' % m.groups(0)[0]), s)

class RSSProcessor(HTMLParser):
    def reset(self):
        self.text = []
        self.__in_hlink = False
        HTMLParser.reset(self)

    def handle_data(self, text):
        if not self.__in_hlink:
            self.text.append(text)

    def handle_charref(self, ref):
        self.text.append('&#' + ref)

    def handle_starttag(self, tag, method, attr):
        if tag == 'a' and attr and dict(attr).get('class', '') == "headerlink":
            self.__in_hlink = True
            return
        if attr:
            self.text.append('<%s %s>' % (tag, ' '.join('%s="%s"' % z for z in attr)))
        else:
            self.text.append('<%s>' % tag)

    def handle_endtag(self, tag, method):
        if tag == 'p':
            import pdb
            pdb.set_trace()
        if tag == 'a' and self.__in_hlink:
            self.__in_hlink = False
        else:
            self.text.append('</%s>' % tag)

    def unknown_endtag(self, tag):
        self.text.append('</%s>' % tag)

def fix_rss(text):
    return re.sub('''<a class=['"]headerlink['"] .*?</a>''', '', text)

if __name__ == '__main__':
    print(fix_rss(open(sys.argv[1], 'r').read()))
