from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys

class TrackWindow(QDialog):
    def __init__(self,parent=None,minval=0, numtracks = 0):
        QDialog.__init__(self,parent)
        #self.resize(QtCore.QSize(QtCore.QRect(0,0,194,86).size()).expandedTo(Dialog.minimumSizeHint()))
        self.setWindowTitle("Change track range")
        #self.setGeometry(10,10,175,33)        

        self.hboxlayout = QHBoxLayout()
        self.hboxlayout.setMargin(0)
        self.hboxlayout.setSpacing(6)

        self.label = QLabel("Start value")
        self.hboxlayout.addWidget(self.label)

        self.frombox = QSpinBox()
        self.frombox.setValue(minval)
        self.hboxlayout.addWidget(self.frombox)
        
        self.hboxlayout2 = QHBoxLayout()
        self.checkbox = QCheckBox("Add seperator ['/']")
        self.numtracks = QLineEdit()
        self.numtracks.setEnabled(False)
        self.numtracks.setMaximumWidth(50)
        self.hboxlayout2.addWidget(self.checkbox)
        self.hboxlayout2.addWidget(self.numtracks)
        
        self.hboxlayout3 = QHBoxLayout()
        self.ok = QPushButton("OK")
        self.cancel=QPushButton("Cancel")
        self.hboxlayout3.addWidget(self.ok)
        self.hboxlayout3.addWidget(self.cancel)
        
        self.vbox = QVBoxLayout(self)
        self.vbox.addLayout(self.hboxlayout)
        self.vbox.addLayout(self.hboxlayout2)
        self.vbox.addLayout(self.hboxlayout3)
        
        self.setLayout(self.vbox)
        self.connect(self.ok,SIGNAL('clicked()'),self.dostuff)
        self.connect(self.cancel,SIGNAL('clicked()'),self.close)
        self.connect(self.checkbox, SIGNAL("stateChanged(int)"), self.setedit)
        
        if numtracks != 0:
            self.checkbox.setCheckState(Qt.Checked)
            self.numtracks.setText(unicode(numtracks))
        
    
    def setedit(self, val):
        print val
        if val == 2:
            self.numtracks.setEnabled(True)
        else:
            self.numtracks.setEnabled(False)
        
    def dostuff(self):
        if self.checkbox.checkState() == 2:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), unicode(self.numtracks.text())])
        else:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), ""])
        self.close()
        
        
#app=QApplication(sys.argv)
#qb=TrackWindow(None,12,23)
#qb.show()
#app.exec_()