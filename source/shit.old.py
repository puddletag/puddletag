from PyQt4 import QtGui,QtCore
import sys, audioinfo,os, copy
from subprocess import Popen
import myini

class witem(QtGui.QTableWidgetItem):
    info=None
    def __init__(self,text="", tabletype = QtGui.QTableWidgetItem.Type):
        QtGui.QTableWidgetItem.__init__(self,text,tabletype)

class KTGFrame(QtGui.QGroupBox):
    def __init__(self,title,parent=None):
        QtGui.QGroupBox.__init__(self,parent)


        self.artist= QtGui.QLabel('Artist')
        title = QtGui.QLabel('Title')
        album = QtGui.QLabel('Album')

        self.titleEdit = QtGui.QComboBox()
        self.artistEdit= QtGui.QComboBox()
        self.albumEdit = QtGui.QComboBox()

        grid = QtGui.QGridLayout()
        #grid.setSpacing(2)

        grid.addWidget(self.artist, 1, 0)
        grid.addWidget(self.artistEdit, 1, 1)

        grid.addWidget(title, 2, 0)
        grid.addWidget(self.titleEdit, 2, 1)

        grid.addWidget(album, 3, 0)
        grid.addWidget(self.albumEdit, 3, 1,)
        
        grid.setColumnStretch(1,2)
        self.setLayout(grid)
    
            
class tableshit(QtGui.QTableWidget):
    def __init__(self,rows,column,parent=None):
        QtGui.QTableWidget.__init__(self,rows,column,parent)
    
    def keyPressEvent (self, event):
        row=self.currentRow()
        column=self.currentColumn()
        if event.key()==QtCore.Qt.Key_Return:
            self.setCurrentCell(row+1,column)
            self.editItem(self.item(row+1,column))
        QtGui.QTableWidget.keyPressEvent(self,event)

class mywindow(QtGui.QWidget):
    def __init__(self,parent=None):
        QtGui.QWidget.__init__(self,parent)
        self.resize(300,800)
        self.mytable=tableshit(0,5,self)
        for z in range(self.mytable.columnCount()):
            self.mytable.setColumnWidth(z,myini.columnwidth[z])
            
        self.mytable.setHorizontalHeaderLabels(["Artist","Title","Album","Track","Year"])
        self.mytable.move(500,500)
        
        self.group=KTGFrame(self)
        self.group.resize(500,300)
        self.group.setMaximumSize(300,300)
        self.group.setMinimumSize(300,300)
        grid = QtGui.QGridLayout()
        grid.addWidget(self.group,0,0)
        grid.setColumnMinimumWidth(0,300)
        grid.addWidget(self.mytable,0,1,2,1)
        self.setLayout(grid)
        self.connect(self.mytable, QtCore.SIGNAL('cellDoubleClicked(int,int)'), self.playfile)       
        self.connect(self.mytable, QtCore.SIGNAL('cellClicked(int,int)'), self.filltext)       
        

    def filltext(self,row,column):

        prevartist=""
        prevtitle=""
        prevalbum=""
        
        for z in (self.group.artistEdit,self.group.albumEdit,self.group.titleEdit):
            z.clear()
            z.setEditable(True)
            
        for idx in self.mytable.selectedItems():
            what=audioinfo.Tag(idx.info["filename"])
            what.gettags()
            if what["artist"]!=prevartist: self.group.artistEdit.addItem(what["artist"]) 
            if what["album"]!=prevalbum: self.group.albumEdit.addItem(what["album"])
            if what["title"]!=prevtitle: self.group.titleEdit.addItem(what["title"]) 
            prevartist=what["artist"]
            prevtitle=what["title"]
            prevalbum=what["album"]
        
    def filltable(self,filename):    
        taginfo=[]
        row=0
        for z in os.listdir(filename):
            what=audioinfo.Tag()
            what.link(os.path.join(filename,z))
            if what.filetype is not(None):
                self.mytable.setRowCount(row+1)
                what.gettags()
                for z in what.tags:
                    foo=witem()
                    if what[z] is None: 
                        foo.setText("")
                    else:
                        foo.setText(unicode(what[z]))
                    foo.info=copy.copy(what.info)
                    for y in range(self.mytable.columnCount()):
                        column=self.mytable.horizontalHeaderItem(y)
                        if unicode(column.text()).lower()==z:
                            self.mytable.setItem(row,y,foo)
                row+=1
        self.mytable.setSortingEnabled(True)
        
        
    def playfile(self):
        li=["xmms", "-e"]
        for z in self.mytable.selectedItems():        
            li.append(z.info["filename"])            
        Popen(li)
    
    def changetag(self,row,column):
        filename=self.mytable.item(row,column).info["filename"]
        tagvalue=unicode(self.mytable.item(row,column).text())
        shat=audioinfo.Tag()
        shat.link(filename)
        shat.gettags()
        tagname=unicode(self.mytable.horizontalHeaderItem(column).text())
        tagname=tagname.lower()
        shat.tags[tagname]=tagvalue
        #shat.writetags()
               
    def closeEvent(self, event):
        what=open("myini.py", "w+")
        what.seek(0)
        myli=[self.mytable.columnWidth(z) for z in range(self.mytable.columnCount())]
        what.write("columnwidth=" + str(myli) + "\n")
        what.close()
        event.accept()
    


class mainwin(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        opendir= QtGui.QAction(QtGui.QIcon('open.png'), 'Open Folder', self)
        opendir.setShortcut('Ctrl+O')
        self.connect(opendir, QtCore.SIGNAL('triggered()'), self.OpenFolder)
        
        savefiles = QtGui.QAction(QtGui.QIcon('open.png'), 'Save', self)
        opendir.setShortcut('Ctrl+')
        self.connect(opendir, QtCore.SIGNAL('triggered()'), self.OpenFolder)

        self.statusBar()

        menubar = self.menuBar()
        file = menubar.addMenu('&File')
        file.addAction(opendir)
        
        self.cenwid=mywindow()
        self.setCentralWidget(self.cenwid)
        self.connect(self.cenwid.mytable,QtCore.SIGNAL('cellChanged (int,int)'),self.cenwid.changetag)
        #self.connect(self.filedlg,QtCore.SIGNAL('currentChanged',thenewfilename))
        
        
        
    def OpenFolder(self):
        filedlg=QtGui.QFileDialog()
        filedlg.setFileMode(filedlg.DirectoryOnly)
        filename = unicode(filedlg.getExistingDirectory(self, 'OpenFolder','/media/multi/',QtGui.QFileDialog.ShowDirsOnly))
        self.cenwid.filltable(filename)
        
        
app=QtGui.QApplication(sys.argv)
#filename=sys.argv[-1]

#while os.path.isdir(filename)==False:
    #print "Please enter a valid folder name or press enter to exit:"    
    #filename=raw_input()
    #if filename=="":sys.exit()
    
qb=mainwin()
qb.show()

app.exec_()
        
        


                 
