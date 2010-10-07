# -*- coding: utf-8 -*-
from distutils.core import setup
import sys, puddlestuff

setup(name='puddletag',
      version=puddlestuff.version_string,
      author='concentricpuddle',
      author_email='concentricpuddle@gmail.com',
      url='http://puddletag.sourceforge.net',
      download_url='https://sourceforge.net/projects/puddletag/files/latest',
      description='A tag editor for Linux based on Mp3tag.',
      packages = ['puddlestuff', 'puddlestuff.mainwin',
                    'puddlestuff.libraries', 'puddlestuff.audioinfo',
                    'puddlestuff.tagsources'],
      keywords='tagging ogg mp3 apev2 mp4',
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
    #shortcuts=['puddletag.desktop'],
    data_files=[('share/pixmaps/', ('puddletag.png',)),
                ('share/applications', ('puddletag.desktop',))]
    #package_dir={'puddlestuff.data': 'puddlestuff/data'},
    #package_data={'puddlestuff.data': ['puddlestuff/data/shortcuts', 'puddlestuff/data/menus']}
     )