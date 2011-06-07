# -*- coding: utf-8 -*-
import subprocess, re
from os.path import dirname
version_string = '0.10.6'
version = (0, 10, 6)

try:
    filedir = dirname(dirname(__file__))
    info = subprocess.Popen(['svn', 'info', filedir], 
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    revision = int(re.search(u'Revision: (\d+)',
        info.stdout.read()).groups()[0])
except (EnvironmentError, AttributeError):
    revision = None