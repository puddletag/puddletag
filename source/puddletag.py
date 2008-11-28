#!/usr/bin/env python
import sys
from PyQt4.QtGui import QApplication

import puddlestuff


if __name__ == "__main__":
    app = QApplication(sys.argv)    
    filename = sys.argv[1:]
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")   
    
    from puddlestuff.puddletag import MainWin
    qb = MainWin()
    qb.show()
    qb.rowEmpty()
    qb.openFolder(filename)
    app.exec_()