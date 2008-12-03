#!/usr/bin/env python
import sys
from PyQt4.QtGui import QApplication, QPixmap, QSplashScreen

import puddlestuff
from puddlestuff import resource
__version__ = 0.3

if __name__ == "__main__":
    app = QApplication(sys.argv)    
    filename = sys.argv[1:]
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")   
    
    from puddlestuff.puddletag import MainWin
    qb = MainWin()
    qb.rowEmpty()
    if filename:
        pixmap = QPixmap(':/puddlelogo.png')
        splash = QSplashScreen(pixmap)
        splash.show()
        QApplication.processEvents()
        qb.openFolder(filename)
        qb.show()
        splash.finish(qb)
    else:
        qb.show()
    app.exec_()