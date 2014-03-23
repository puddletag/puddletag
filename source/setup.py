# -*- coding: utf-8 -*-
import sys
#Using the setuptools setup doesn't include everything
#in the manifest.

if 'sdist' in sys.argv:
    from distutils.core import setup
else:
    try:
        from setuptools import setup
    except ImportError:
        from distutils.core import setup

import puddlestuff
setup(
    name='puddletag',
    version=puddlestuff.version_string,
    author='concentricpuddle',
    author_email='concentricpuddle@gmail.com',
    url='http://puddletag.sourceforge.net',
    download_url='https://sourceforge.net/projects/puddletag/files/latest',
    description='An simple, powerful audio tag editor.',
    packages = ['puddlestuff', 'puddlestuff.mainwin',
        'puddlestuff.libraries', 'puddlestuff.audioinfo',
        'puddlestuff.tagsources', 'puddlestuff.tagsources.mp3tag',
        'puddlestuff.masstag', 'puddlestuff.plugins'],

    keywords='tagging ogg mp3 apev2 mp4 id3',
    license='GNU General Public License v2',
    classifiers=['Development Status :: 2 - Unstable',
        'Intended Audience :: Users',
        'Natural Language :: English',
        'Operating System :: GNU/Linux',
        'Programming Language :: Python :: 2.6',
        'License :: OSI Approved :: GNU General Public License v3',
        'Topic :: Tagging',
        ],
        
    scripts = ['puddletag'],
    data_files=[('share/pixmaps/', ('puddletag.png',)),
        ('share/applications/', ('puddletag.desktop',)),
        ('share/man/man1/', ('puddletag.1',))]
     )
