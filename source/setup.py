from distutils.core import setup
from PyPIBrowser.constants import __version__


setup(
    name="puddletag",
    version=0.2
    author="concentricpuddle",
    author_email="cpuddle@users.sourceforge.net",
    url="https://puddletag.sourceforge.net"
    description="A semi-good music tag editor",
    long_description="puddletag is a music tag editor that tries not to suck "
                     "currently it supports mp3 and ogg files "
                     "and it uses pyqt4 for the gui.",
    scripts=["puddletag.py"],
    packages=["PuddleTag"]}