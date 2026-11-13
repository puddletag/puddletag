# -*- coding: utf-8 -*-

from setuptools import setup

def _runtime_dependencies():
    """ Read the runtime dependencies from the requirements file """
    with open('requirements.txt') as f:
        return f.read().splitlines()

def _version():
    """ Read the version from the puddlestuff package """
    version = {}
    with open("puddlestuff/__init__.py") as fp:
        exec(fp.read(), version)
    return version['version_string']


def readme():
    with open('README.md') as f:
        return f.read()

setup(
    name='puddletag',
    version=_version(),
    author='puddletag developers',
    url='https://docs.puddletag.net/',
    download_url='https://github.com/puddletag/puddletag',
    description='Powerful, simple, audio tag editor',
    long_description=readme(),
    long_description_content_type='text/markdown',
    packages=['puddlestuff',
              'puddlestuff.mainwin',
              'puddlestuff.libraries',
              'puddlestuff.audioinfo',
              'puddlestuff.tagsources',
              'puddlestuff.tagsources.mp3tag',
              'puddlestuff.masstag',
              'puddlestuff.plugins',
              'puddlestuff.plugins.dupe_fields',
              'puddlestuff.plugins.extended_tags',
              'puddlestuff.plugins.id3_tools',
              'puddlestuff.plugins.modified_time',
              'puddlestuff.plugins.save_tags',
              'puddlestuff.plugins.view_all_fields'],
    package_data={'puddlestuff': ['data/*', 'translations/*.qm'],
                  'puddlestuff.plugins': ['*/info']},
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
    python_requires=">=3.14",
    install_requires=_runtime_dependencies(),
    data_files=[('share/pixmaps/', ['puddletag.png', ]),
                ('share/applications/', ['puddletag.desktop', ]),
                ('share/man/man1/', ['puddletag.1', ])]
)
