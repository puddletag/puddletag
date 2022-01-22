# this module is a hack to overcome BeautifulSoup's tendency to fall on script tags contents
# while we're at it, we also wrap url fetching.


import re
import urllib.error
import urllib.parse
import urllib.request

import lxml.html


def classify(seq, key_func):
    result = {}
    for item in seq:
        key = key_func(item)
        if key in result:
            result[key].append(item)
        else:
            result[key] = [item]
    return result


class SoupWrapper(object):
    def __init__(self, element, source=None):
        self.element = element
        self.source = source

    def find_all(self, *args, **kwargs):
        if isinstance(args[0], dict):
            kwargs.update(args[0])
        if len(args) == 2:
            if isinstance(args[1], dict):
                kwargs.update(args[1])
            else:
                kwargs["class"] = args[1]
        query_items = list(kwargs.items())
        query_items = classify(query_items, lambda x: isinstance(x[1], (str, str)))
        regular_items = query_items.get(True, [])
        re_items = query_items.get(False, [])
        xpath_query = " and ".join(
            "@%s='%s'" % (key, value) for key, value in regular_items
        )
        if xpath_query:
            xpath_query = "[%s]" % xpath_query
        if len(args) == 1 and not isinstance(args[0], dict):
            query = ".//%s%s" % (args[0], xpath_query)
        else:
            query = ".//*%s" % xpath_query
        results = self.element.xpath(query)
        if re_items:
            new_results = []
            for x in results:
                if all(
                    x.attrib and key in x.attrib and re.search(value, x.attrib[key])
                    for key, value in re_items
                ):
                    new_results.append(x)
            results = new_results
        return [SoupWrapper(x) for x in results]

    def find(self, *args, **kwargs):
        r = self.find_all(*args, **kwargs)
        if r:
            return r[0]
        return None

    def __iter__(self):
        for x in self.element:
            yield SoupWrapper(x)

    def __getitem__(self, idx):
        if isinstance(idx, (str, str)):
            if idx in self.element.attrib:
                return self.element.attrib[idx]
            else:
                return self.find(idx)
        if isinstance(idx, int):
            return SoupWrapper(self.element[idx])
        if isinstance(idx, slice):
            return [SoupWrapper(x) for x in self.element[idx]]

    def __getattr__(self, name):
        if name in self.element.attrib:
            return self.element.attrib[name]
        return self.find(name)

    @property
    def string(self):
        return self.element.text_content()

    def all_text(self):
        result = []
        if self.element.text:
            result.append(self.element.text)
        for x in self.element:
            if x.tail:
                result.append(x.tail)
        return "".join(result)

    def all_recursive_text(self, should_continue=lambda node: True):
        r = []
        if self.element.text:
            r.append(self.element.text)
        for node in self:
            if should_continue(node):
                r.append(node.all_recursive_text(should_continue))
            if node.element.tail:
                r.append(node.element.tail)
        return " ".join(r)

    @property
    def contents(self):
        return [SoupWrapper(x) for x in self.element]

    @property
    def name(self):
        return self.element.tag

    @property
    def tag(self):
        return self.element.tag

    @property
    def parent(self):
        return SoupWrapper(self.element.getparent())


def fetch_page(url):
    return urllib.request.urlopen(url).read()


def parse(page):
    p = lxml.html.document_fromstring(page)
    return p


def fetch_parsed(url):
    page = fetch_page(url)
    try:
        p = parse(page)
    except:
        print(url)
        raise
    return p


def fetch_soup(url):
    page = fetch_page(url)
    try:
        p = parse(page)
    except:
        print(url)
        raise
    return SoupWrapper(p, page)
