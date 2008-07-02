from PyQt4.QtGui import *
from PyQt4.QtCore import *
import findfunc
import sys

class ImportWindow(QDialog):
    def __init__(self,parent=None, filename = ""):
        QDialog.__init__(self,parent)
        #self.resize(QtCore.QSize(QtCore.QRect(0,0,194,86).size()).expandedTo(Dialog.minimumSizeHint()))
        self.setWindowTitle("Import tags from file")
        #self.setGeometry(10,10,175,33)        
        
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


        self.connect(self.patterncombo, SIGNAL("editTextChanged(QString)"),self.FillTags)
        self.connect(self.openfile,SIGNAL("clicked()"),self.OpenFile)
        self.connect(self.cancel, SIGNAL("clicked()"),self.close)
        self.connect(self.ok, SIGNAL("clicked()"),self.dostuff)
        
        if filename != "":
            self.OpenFile(filename)
            
    def OpenFile(self, filename = ""):
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
    
    def FillTags(self,string = None):
        self.dicttags = []
        for z in self.lines:
            self.dicttags.append(findfunc.filenametotag(unicode(self.patterncombo.currentText()),z,False))
        self.tags.setPlainText("\n".join([unicode(z) for z in self.dicttags]))
                
    def dostuff(self):
        self.emit(SIGNAL("Newtags"),self.dicttags)
        self.close()
        
#app=QApplication(sys.argv)
#qb=ImportWindow()
#qb.show()
#app.exec_()