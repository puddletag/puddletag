# -*- coding: utf-8 -*-
from distutils.core import setup
import sys, puddlestuff
setup(
    name='puddletag',
      version=puddlestuff.version_string,
      author='concentricpuddle',
      author_email='concentricpuddle@gmail.com',
      url='http://puddletag.sourceforge.net',
      download_url='https://sourceforge.net/projects/puddletag/files/latest',
      description='An audio tagger for GNU/Linux similar to Mp3tag for Windows.',
      packages = ['puddlestuff', 'puddlestuff.mainwin',
        'puddlestuff.libraries', 'puddlestuff.audioinfo',
        'puddlestuff.tagsources', 'puddlestuff.tagsources.mp3tag'],
      keywords='tagging ogg mp3 apev2 mp4 id3',
      license='GNU General Public License v2',
      classifiers=['Development Status :: 2 - Unstable',
        'Intended Audience :: Users',
        'Natural Language :: English',
        'Operating System :: GNU/Linux',
        'Programming Language :: Python :: 2.5',
        'License :: OSI Approved :: GNU General Public License v2',
        'Topic :: Tagging',
        ],
    scripts = ['puddletag'],
    data_files=[('share/pixmaps/', ('puddletag.png',)),
                ('share/applications', ('puddletag.desktop',))]
     )