#Note, change LANG to en.
"""A module that shows how to work with the audioinfo module.
    The main function of this module is the main function
    which basically just does what is described in its docstring."""

from optparse import OptionParser
import sys,os,shutil
from findfunc import *
from audioinfo import Tag

def vararg_callback(option, opt_str, value, parser):
    "command line shit"
    assert value is None
    value = []
    rargs = parser.rargs
    while rargs:
        arg = rargs[0]

        if ((arg[:2] == "--" and len(arg) > 2) or
            (arg[:1] == "-" and len(arg) > 1 and arg[1] != "-")):
            break
        else:
            value.append(arg)
        del rargs[0]

    setattr(parser.values, option.dest, value)


def parseoptions():
    
    usage = "usage: %prog pattern [tag|file] -f filenames [-t=1|0] [-R dir]"
    parser=OptionParser(usage)
    parser.add_option("-f","--filenames",dest="filename",action="callback",help="The filenames of the input files", callback=vararg_callback)
    parser.add_option("-t","--test",dest="test",help="Don't change anything, just print results if set to 0.",type="int",default=1)
    parser.add_option("-R","--renamedir",dest="renamedir",help="Rename the directory according to your pattern.",default=0)
    (options,args)=parser.parse_args()
    
    try:
        if sys.argv[1]==None: 
            parser.print_help()
            parser.error("Please enter a pattern.")
        elif options.renamedir!=0:
            renamedir(options.renamedir,sys.argv[1])
            sys.exit()
        elif options.filename==[]:
            parser.print_help()
            parser.error("Please enter a filename.")
        elif sys.argv[2]!='tag' and sys.argv[2]!='file':        
            parser.print_help()
            parser.error("Please enter a value to choose to convert a (tag to filename) or to (extract tags from the filename.)")
    except IndexError:
            parser.print_help()
            sys.exit()
    return (options,args)
    
    
def main():
    """Call the program from the command line with the
    filenames of the files that are to be renamed
    according to a rule that you specify. Or have the
    tags extracted from the filename.
    
    """
    
    
    (options,args)=parseoptions()
    tag=Tag()
    inputfiles=options.filename
    pattern=sys.argv[1]
    test=options.test
    newfiles=[]        
    mvmsg=[]
    
    #Rename the file using the tags.
    if sys.argv[2]=="tag":
        for z in inputfiles:
            if tag.link(z)==None:
                newfilename=tagtofilename(pattern,z,True)
                try:
                    if test==0: os.rename(z,newfilename)
                    else:
                        mvmsg.append("Move " + unicode(z,'latin-1') + " to " + newfilename)
                except IOError:
                    print "Could not move " + z + " to " + newfilename
                    print "Permission Denied"
        print "\n".join(mvmsg)
    #Extract tags using the filename                
    elif sys.argv[2]=="file":
        for z in inputfiles:
            if tag.link(z)==None:
                tag.gettags()
                tag.tags.update(filenametotag(pattern,os.path.basename(z),True))
                if test==0:tag.writetags()
                else:print filenametotag(pattern,os.path.basename(z),True)
    
        
def renamedir(sourcedir,pattern):
    '''Rename a directory full of tracks from the same album
    according to pattern.'''
    
    tag=Tag()
    pathsep=os.path.sep
    joinpath=os.path.join
    
    #Get the files
    try:
        files = [joinpath(sourcedir,z) for z in os.listdir(sourcedir) 
                    if tag.link(joinpath(sourcedir,z))==None]
    #If there's a error the directory probably does not exist.
    except OSError: 
        print "The directory does not exist"
        return
    
    #Check if all the music files in sourcedir are from the same album.
    try:    
        tag.link(files[0])
        tag.gettags()
        album=tag["album"]
        
        for z in files[1:]:
            tag.link(z)
            tag.gettags()
            if (tag["album"]!=album) or (tag["album"] is None) or (tag["album"]==""):
                print "The album names do not match"
                print "Stopped at ", z
                return
    except IndexError:
        return
    
    #If a directory name is specified with a trailing slash, we need to remove it
    if sourcedir.endswith(pathsep):
        sourcedir=os.path.dirname(sourcedir)
    
    if sourcedir.rfind(pathsep)!=-1:
        #Get the filename, then find the right "/", remove everything after it. Then join the two
        destdir=joinpath(sourcedir[: sourcedir.rfind(pathsep)], tagtofilename(pattern,files[0]))    
    
    else: destdir=tagtofilename(pattern,files[0])
        
    try:
        os.rename(sourcedir,destdir)
    except OSError:
        print "Could not rename the directory. Check that you have write permission and that it's not currently being accessed."

if __name__ == "__main__":
    try:
        retval = main();
    except KeyboardInterrupt:
        retval = 0;
    sys.exit(retval);
    
