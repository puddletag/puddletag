# -*- coding: utf-8 -*-
import PyRSS2Gen
import datetime
import glob
import os
import re
import shutil
import sys
from subprocess import call


def remove_headerlinks(text):
    return re.sub("""<a class=['"]headerlink['"] .*?</a>""", "", text)


def to_html(fns):
    rst_fns = []
    html_fns = []
    html_dir = "_build/html/"
    for i, fn in enumerate(fns):
        rst_fn = "rss_temp%d.txt" % i
        html_fns.append(os.path.join(html_dir, "rss_temp%d.html" % i))

        shutil.copy(fn, rst_fn)
        rst_fns.append(rst_fn)

    try:
        call(
            ["sphinx-build2", "-q", "-b", "html", "-D", "html_theme=rss", ".", html_dir]
            + rst_fns
        )
    except OSError:
        call(
            ["sphinx-build", "-q", "-b", "html", "-D", "html_theme=rss", ".", html_dir]
            + rst_fns
        )

    list(map(os.remove, rst_fns))

    ret = []
    for html_fn in html_fns:
        html_file = open(html_fn, "r")
        ret.append(remove_headerlinks(html_file.read()))
        html_file.close()
        os.remove(html_fn)

    return ret


def create_rss(files):
    contents = to_html(files)
    titles = [re.search("<h1>(.*?)</h1>", c).groups()[0] for c in contents]

    dates = []
    for filename in files:
        try:
            dates.append([int(z) for z in os.path.basename(filename).split("-")])
        except ValueError:
            pass
    dates = [datetime.datetime(*date) for date in dates]

    items = []
    for filename, title, desc, date in zip(files, titles, contents, dates):
        anchor = get_anchor(desc)
        items.append(
            PyRSS2Gen.RSSItem(
                title=title,
                link="http://puddletag.sourceforge.net/news.html#%s" % anchor,
                description="\n".join(desc.split("\n")[1:]),
                pubDate=date,
                author="concentricpuddle",
            )
        )

    rss = PyRSS2Gen.RSS2(
        title="puddletag news feed",
        link="http://puddletag.sourceforge.net",
        description="The latest news about puddletag: " "A tag-editor for GNU/Linux.",
        lastBuildDate=datetime.datetime.now(),
        docs=None,
        items=items,
    )

    return rss


def get_anchor(text):
    anchor = re.search("""<div class="section" id=['"](.+?)['"]>""", text).groups()[0]
    return anchor


def create_page(files):
    out = [
        """.. include:: subs.txt

News
^^^^


.. |rss| image:: feed.png
    :width: 27px
    :height: 28px
    :alt: RSS Image
    :class: text


:download:`RSS Feed <rss.xml>`

"""
    ]

    texts = [open(f, "r").read() for f in files]

    for t in texts:
        out.append("\n\n----\n\n" + t + "\n")

    return "".join(out)


class WriteXmlMixin:
    def write_xml(self, outfile, encoding="utf8"):
        from xml.sax import saxutils

        handler = saxutils.XMLGenerator(outfile, encoding)
        handler.startDocument()
        self.publish(handler)
        handler.endDocument()

    def to_xml(self, encoding="utf8"):
        try:
            import cStringIO as StringIO
        except ImportError:
            import StringIO
        f = StringIO.StringIO()
        self.write_xml(f, encoding)
        return f.getvalue()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        f = open("_build/html/news.html", "r+")
        text = f.read()
        f.seek(0)
        f.write(text.replace("_downloads/rss.xml", "rss.xml"))
        f.truncate()
        f.close()
        shutil.move("rss.xml", "_build/html/rss.xml")
    else:
        files = sorted(glob.glob("news/*"), reverse=True)
        if not os.path.isdir("_build/html/"):
            os.makedirs("_build/html/")
        rss = create_rss(files)
        rss.write_xml(open("rss.xml", "w"))

        news = open("news.txt", "w")
        news.write(create_page(files))
        news.close()
