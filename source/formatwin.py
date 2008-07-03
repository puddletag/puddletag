from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys, findfunc

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
        self.connect(self.ok,SIGNAL('clicked()'),self.doStuff)
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
        
    def doStuff(self):
        if self.checkbox.checkState() == 2:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), unicode(self.numtracks.text())])
        else:
            self.emit(SIGNAL("newtracks"),[self.frombox.value(), ""])
        self.close()
        
class ImportWindow(QDialog):
    def __init__(self,parent=None, filename = ""):
        QDialog.__init__(self,parent)
        self.setWindowTitle("Import tags from file")
        
        self.grid = QGridLayout()
        
        self.label = QLabel("File")
        self.grid.addWidget(self.label,0,0)

        self.label = QLabel("Tags")
        self.grid.addWidget(self.label,0,2)


        self.file = QTextEdit()
        self.grid.addWidget(self.file,1,0,1,2)        

        self.tags = QTextEdit()
        self.grid.addWidget(self.tags,1,2,1,2)        
        
        self.label = QLabel("Pattern")
        self.grid.addWidget(self.label,2,0,)
        
        self.hbox = QHBoxLayout()
        
        self.patterncombo = QComboBox()
        self.patterncombo.setEditable(True)
        self.patterncombo.setDuplicatesEnabled(False)
        
        self.ok = QPushButton("OK")
        self.cancel = QPushButton("Cancel")
        
        self.openfile = QPushButton("Open File")
        
        self.hbox.addWidget(self.openfile)
        self.hbox.addWidget(self.patterncombo,1)
        self.hbox.addWidget(self.ok)
        self.hbox.addWidget(self.cancel)
        
        self.grid.addLayout(self.hbox,3,0,1,4)
        self.setLayout(self.grid)


        self.connect(self.patterncombo, SIGNAL("editTextChanged(QString)"),self.fillTags)
        self.connect(self.openfile,SIGNAL("clicked()"),self.openFile)
        self.connect(self.cancel, SIGNAL("clicked()"),self.close)
        self.connect(self.ok, SIGNAL("clicked()"),self.doStuff)
        
        if filename != "":
            self.openFile(filename)
            
    def openFile(self, filename = ""):
        if filename == "" or filename is None:
            filedlg = QFileDialog()
            filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder','/media/multi/'))
        if filename != "":
            f = open(filename)
            i = 0
            self.lines = f.readlines()
            self.file.setPlainText("".join(self.lines))
            f.close()                
    
    def fillTags(self,string = None):
        self.dicttags = []
        for z in self.lines:
            self.dicttags.append(findfunc.filenametotag(unicode(self.patterncombo.currentText()),z,False))
        self.tags.setPlainText("\n".join([unicode(z) for z in self.dicttags]))
                
    def doStuff(self):
        self.emit(SIGNAL("Newtags"), self.dicttags)
        self.close()        
#app=QApplication(sys.argv)
#qb=TrackWindow(None,12,23)
#qb.show()
#app.exec_()