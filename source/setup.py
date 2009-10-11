from distutils.core import setup
import sys

setup(name='puddletag',
      version='0.8.0',
      author='concentricpuddle',
      author_email='concentricpuddle@gmail.com',
      url='http://puddletag.sourceforge.net',
      download_url='https://sourceforge.net/projects/puddletag/files/latest',
      description='A tag editor for Linux based on Mp3tag.',
      long_description='None',
      #package_dir={'puddletag': 'puddlestuff'},
      packages = ['puddlestuff', 'puddlestuff.mainwin', 'puddlestuff.duplicates',
                    'puddlestuff.libraries', 'puddlestuff.audioinfo'],
      keywords='tagging ogg mp3 apev2 mp4',
      license='GNU General Public License v3',
      classifiers=['Development Status :: 2 - Unstable',
                   'Intended Audience :: Users',
                   'Natural Language :: English',
                   'Operating System :: GNU/Linux',
                   'Programming Language :: Python :: 2.5',
                   'License :: OSI Approved :: GNU General Public License v2',
                   'Topic :: Tagging',
                  ],
        scripts = ['puddletag', 'console']
     )