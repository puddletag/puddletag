# -*- coding: utf-8 -*-
import sys

# Using the setuptools setup doesn't include everything
# in the manifest.

if 'sdist' in sys.argv:
    from distutils.core import setup
else:
    try:
        from setuptools import setup
    except ImportError:
        from distutils.core import setup

with open('requirements.txt') as f:
    required = f.read().splitlines()

import puddlestuff

setup(
    name='puddletag',
    version=puddlestuff.version_string,
    author='puddletag developers',
    url='https://docs.puddletag.net/',
    download_url='https://github.com/puddletag/puddletag',
    description='Powerful, simple, audio tag editor',
    packages=['puddlestuff', 'puddlestuff.mainwin',
              'puddlestuff.libraries', 'puddlestuff.audioinfo',
              'puddlestuff.tagsources', 'puddlestuff.tagsources.mp3tag',
              'puddlestuff.masstag', 'puddlestuff.plugins'],
    keywords='tagging ogg mp3 apev2 mp4 id3',
    license='GNU General Public License v3 or later (GPLv3+)',
    classifiers=['Development Status :: 5 - Production/Stable',
                 'Intended Audience :: End Users/Desktop',
                 'Natural Language :: English',
                 'Operating System :: POSIX :: Linux',
                 'Programming Language :: Python :: 3 :: Only',
                 'Topic :: Multimedia :: Sound/Audio :: Editors',
                 ],
    scripts=['puddletag'],
    install_requires=required,
    data_files=[('share/pixmaps/', ['puddletag.png', ]),
                ('share/applications/', ['puddletag.desktop', ]),
                ('share/man/man1/', ['puddletag.1', ])]
)
