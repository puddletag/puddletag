# -*- coding: utf-8 -*-
#
# puddletag documentation build configuration file, created by
# sphinx-quickstart on Tue Mar 22 20:40:26 2011.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys, os

import sphinx_bootstrap_theme

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# sys.path.insert(0, os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
# sys.path.append(os.path.abspath('exts'))

extensions = []

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = ".txt"

# The encoding of source files.
# source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = "index"

# General information about the project.
project = u"puddletag"
copyright = u"2011, concentricpuddle"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = "1.0.2"
# The full version, including alpha/beta/rc tags.
release = "0.10.3"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
# language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
# today = ''
# Else, today_fmt is used as the format for a strftime call.
# today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build"]

# The reST default role (used for this markup: `text`) to use for all documents.
# default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
# add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
# add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
# show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# A list of ignored prefixes for module index sorting.
# modindex_common_prefix = []


# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "bootstrap"
html_theme_path = sphinx_bootstrap_theme.get_html_theme_path() + ["_templates"]

# agogo/theme.conf
# basic/theme.conf
# default/theme.conf
# epub/theme.conf
# haiku/theme.conf
# nature/theme.conf
# scrolls/theme.conf
# sphinxdoc/theme.conf
# traditional/theme.conf


# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    "navbar_site_name": "puddletag",
    "navbar_links": [
        ("Home", "index"),
        ("Download", "download"),
        ("News", "news"),
        ("Documentation", "docs"),
        ("Development", "https://github.com/puddletag/puddletag", True),
        ("Issue Tracker", "https://github.com/puddletag/puddletag/issues", True),
        ("Screenshots", "screenshots"),
        ("About", "about"),
    ],
    "navbar_sidebarrel": False,
    "globaltoc_includehidden": "false",
    "navbar_pagenav": False,
    "source_link_position": "nothing",
    "globaltoc_depth": -1,
    "bootswatch_theme": "flatly",
}

# Add any paths that contain custom themes here, relative to this directory.
# html_theme_path = ['_templates']

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = "puddletag"

# A shorter title for the navigation bar.  Default is the same as html_title.
# html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
# html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
# html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
# html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
# html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
# html_sidebars = {}
html_sidebars = {
    "source/filter": ["my_sidebar.html"],
    "source/function": ["my_sidebar.html"],
    "source/id3": ["my_sidebar.html"],
    "source/images": ["my_sidebar.html"],
    "source/menus": ["my_sidebar.html"],
    "source/plugins": ["my_sidebar.html"],
    "source/preferences": ["my_sidebar.html"],
    "source/tagsources": ["my_sidebar.html"],
    "source/tagsource.tar.gz": ["my_sidebar.html"],
    "source/tags": ["my_sidebar.html"],
    "source/tut3": ["my_sidebar.html"],
    "source/tut4": ["my_sidebar.html"],
    "source/tut5": ["my_sidebar.html"],
}

# Additional templates that should be rendered to pages, maps page names to
# template names.
# html_additional_pages = {'about': 'non-doc.html'}

# If false, no module index is generated.
html_domain_indices = ["about", "download", "index", "screenshots", "news"]
# unused_docs = html_domain_indices + ['subs']

# If false, no index is generated.
# html_use_index = True

# If true, the index is split into individual pages for each letter.
# html_split_index = False

# If true, links to the reST sources are added to the pages.
# html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
# html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
html_show_copyright = False

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
# html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
# html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = "puddletagdoc"


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
# latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
# latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
    (
        "index",
        "puddletag.tex",
        u"puddletag Documentation",
        u"concentricpuddle",
        "manual",
    ),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
# latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
# latex_use_parts = False

# If true, show page references after internal links.
# latex_show_pagerefs = False

# If true, show URL addresses after external links.
# latex_show_urls = False

# Additional stuff for the LaTeX preamble.
# latex_preamble = ''

# Documents to append as an appendix to all manuals.
# latex_appendices = []

# If false, no module index is generated.
# latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ("index", "puddletag", u"puddletag Documentation", [u"concentricpuddle"], 1)
]
