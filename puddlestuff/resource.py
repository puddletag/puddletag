# -*- coding: utf-8 -*-

from os.path import abspath, dirname, join

from PyQt5.QtCore import QDir


package_path = abspath(dirname(__file__))
QDir.addSearchPath('data', join(package_path, 'data'))
QDir.addSearchPath('icons', join(package_path, 'data'))
QDir.addSearchPath('translations', join(package_path, 'translations'))
