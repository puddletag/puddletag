#!/usr/bin/env python
import sys
from PyQt4.QtGui import QApplication, QPixmap, QSplashScreen

from puddlestuff import resource
from puddlestuff.puddletag import MainWin
__version__ = "0.3.1"

if __name__ == "__main__":
    app = QApplication(sys.argv)    
    filename = sys.argv[1:]
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")   
    
    pixmap = QPixmap(':/puddlelogo.png')
    splash = QSplashScreen(pixmap)
    splash.show()
    QApplication.processEvents()

    qb = MainWin()
    qb.rowEmpty()
    if filename:
        qb.openFolder(filename)
        qb.show()
        splash.finish(qb)
    else:
        qb.show()
    app.exec_()
