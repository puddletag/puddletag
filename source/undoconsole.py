"""A module that allows you to undo changes you made to files.
There are two functions, undochanges and writechanges. 
See their docstrings for info."""

import copy

def undochanges():
    """Undo's changes made to a files. Say you had a bunch of files who's tags you want to change,
    but whose tags you want to reserve just in case you mess up.
    
    First you'd put all the tags from the files in a dictionary in the format {filename:tags}
    see the audioinfo module for how tags must be specified.
    
    Then you'd call writechanges("tag",yourdictionary}, which would then save your tags to
    a dictionary in this module.
    
    After which, provided you haven't moved the files or anything like that, you call this 
    function and it will undo what you did."""
    #Do not change the next two lines. If you've added or removed any lines, then you'll need to make the writechanges function reflect this by changing the line that has "mydict" to the line below this.
    mydict = {'/home/keith/Jojo/Jojo - City Lights.mp3': {'album': u'', 'publisher': u'Blackground Records', 'artist': u'City Lights', 'track': 0, 'title': u'Jojo', 'year': '2004', 'genre': 'Pop'}, '/home/keith/Jojo/Jojo - The High Road.mp3': {'album': u'', 'publisher': u'Blackground Records', 'artist': u'The High Road', 'track': None, 'title': u'Jojo', 'year': '2006', 'genre': 'Blues'}, '/home/keith/Jojo/Jojo - Leave(Get Out).mp3': {'album': u'', 'publisher': u'Blackground Records', 'artist': u'Leave(Get Out)', 'track': 7, 'title': u'Jojo', 'year': '2006', 'genre': 'Pop'}, '/home/keith/Jojo/Jojo - Beautiful Girls.mp3': {'album': u'', 'publisher': u'Blackground Records', 'artist': u'Beautiful Girls', 'track': None, 'title': u'Jojo', 'year': '2004', 'genre': 'Pop'}, '/home/keith/Jojo/Jojo - Too Little Too Late.mp3': {'album': u'Our Frisco', 'publisher': u'Lamingtone', 'artist': u'Too Little Too Late', 'track': 2, 'title': u'Jojo', 'year': '1989', 'genre': 'Rock'}, '/home/keith/Jojo/Jojo - Leave.mp3': {'album': u'', 'publisher': u'Blackground Records', 'artist': u'Leave', 'track': None, 'title': u'Jojo', 'year': '2006', 'genre': 'Pop'}, '/home/keith/Jojo/Jojo - How To Touch A Girl.mp3': {'album': u'The High Road', 'publisher': u'Blackground Records', 'artist': u'How To Touch A Girl', 'track': 11, 'title': u'Jojo', 'year': '2006', 'genre': 'Pop'}, '/home/keith/Jojo/Jojo - Anything.mp3': {'album': u'Too Little Too L8', 'publisher': u'Blackground Records', 'artist': u'Anything', 'track': 2, 'title': u'Jojo', 'year': '2006', 'genre': 'Genre'}, '/home/keith/Jojo/Jojo - Never Say Goodbye.mp3': {'album': u'', 'publisher': u'Blackground Records', 'artist': u'Never Say Goodbye', 'track': 0, 'title': u'Jojo', 'year': '2006', 'genre': 'Pop'}, "/home/keith/Jojo/Jojo - Baby It's You.mp3": {'album': u'', 'publisher': u'Blackground Records', 'artist': u"Baby It's You", 'track': 2, 'title': u'Jojo', 'year': '2004', 'genre': 'Pop'}}
    operation = "tag"
    
    #Until here unless you have studied the writechanges function
    if operation=="tag":
        temptags={}
        from audioinfo import Tag
        for filename in mydict:
            tag=Tag()
            if tag.link(filename)==None:
                tag.gettags()
                temptags[filename]=copy.deepcopy(tag.tags)
                tag.tags=copy.deepcopy(mydict[filename])
                tag.writetags()
        writechanges("tag",temptags)
    
    elif operation=="file":
        temp={}
        for filename in mydict:
            shutil.move(filename,mydict[filename])
            temp[mydict[filename]]=filename
        writechanges("file",temp)
        
def writechanges(op,info):
    if __file__[-4:]==".pyc":
        modpath=__file__[:-1]
    else:
        modpath=__file__
    f=open(modpath)
    lines=f.readlines()
    lines[19]="    mydict = " + unicode(info) + "\n"
    lines[20]='    operation = "' + op + '"\n'
    f.close()
    f=open(modpath,"w")
    f.writelines(lines)