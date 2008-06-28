import eyeD3, os, pdb
import ogg.vorbis as vorbis
class Tag:
    """Class that operates on audio file tags.
    Currently supports ogg and mp3 files.
    call with the filename of the audio file
    that you want to be used."""
    
    #Stores the tag info in the format {tag:tag value}
    tags={}
    info={}
    __ids= { "TIT1": "grouping",
            "TIT2": "title",
            "TIT3": "version",
            "TPE1": "artist",
            "TPE2": "performer", 
            "TPE3": "conductor",
            "TPE4": "arranger",
            "TEXT": "lyricist",
            "TCOM": "composer",
            "TENC": "encodedby",
            "TALB": "album",
            "TRCK": "track",
            "TPOS": "discnumber",
            "TSRC": "isrc",
            "TCOP": "copyright",
            "TPUB": "organization",
            "TSST": "part",
            "TOLY": "author",
            "TMOO": "mood",
            "TBPM": "bpm",
            "TDOR": "originaldate",
            "TOAL": "originalalbum",
            "TOPE": "originalartist",
            "WOAR": "website",
            "TXXX": "user",
            "TRSN" : "radiostationname",
            "TMED" : "mediatype",
            "TSOT" : "titlesortorder",
            "TOFN" : "originalfilename",
            "TSSE" : "encodingsettings",
            "TIPL" : "peopleinvolved",
            "TDRL" : "releasetime",
            "TRSO" : "radioowener",
            "TKEY" : "initialkey",
            "TSOA" : "albumsortorder",
            "TPRO" : "producednotice",
            "TDTG" : "taggingtime",
            "TDEN" : "encodingtime",
            "TSOP" : "performersortorder",
            "TCON" : "contenttype",
            "TOWN" : "fileowner",
            "TDLY" : "playlistdelay",
            "TLEN" : "length",
            "TFLT" : "filetype",
            "TMCL" : "musiciancredits",
            "TLAN" : "language",
            "TDRC" : "date"
            
            
            # "language" should not make to TLAN. TLAN requires
            # an ISO language code, and QL tags are freeform.
            }
    __revids = {"encodingsettings" : "TSSE",
                "producednotice" : "TPRO",
                "performer" : "TPE2",
                "titlesortorder" : "TSOT",
                "radiostationname" : "TRSN",
                "filetype" : "TFLT",
                "lyricist" : "TEXT",
                "performersortorder" : "TSOP",
                "composer" : "TCOM",
                "encodedby" : "TENC",
                "discnumber" : "TPOS",
                "releasetime" : "TDRL",
                "album" : "TALB",
                "contenttype" : "TCON",
                "mood" : "TMOO",
                "copyright" : "TCOP",
                "author" : "TOLY",
                "length" : "TLEN",
                "encodingtime" : "TDEN",
                "version" : "TIT3",
                "originalalbum" : "TOAL",
                "website" : "WOAR",
                "conductor" : "TPE3",
                "radioowener" : "TRSO",
                "playlistdelay" : "TDLY",
                "initialkey" : "TKEY",
                "mediatype" : "TMED",
                "albumsortorder" : "TSOA",
                "part" : "TSST",
                "track" : "TRCK",
                "user" : "TXXX",
                "isrc" : "TSRC",
                "peopleinvolved" : "TIPL",
                "musiciancredits" : "TMCL",
                "taggingtime" : "TDTG",
                "originalfilename" : "TOFN",
                "originaldate" : "TDOR",
                "originalartist" : "TOPE",
                "language" : "TLAN",
                "artist" : "TPE1",
                "title" : "TIT2",
                "bpm" : "TBPM",
                "arranger" : "TPE4",
                "organization" : "TPUB",
                "fileowner" : "TOWN",
                "grouping" : "TIT1",
                "date" : "TDRC"
                }
    #The filename of the linked file
    filename=None
    #The type of file
    filetype=""
    OGG="ogg"
    MP3="mp3"
            
    def __getitem__(self,key):
        """Get the tag value from self.tags"""
        try:
            return self.tags[key]
        except KeyError:
            pass
            
    def __init__(self,filename=None):
        """Links the file"""
        if filename!=None:
            self.link(filename)
            
    def link(self,filename):
        """Links the file, filename
        returns None if successful.
        1 or 0 if not. Right now those values are meaningless"""
            
        #Get the type of file and set
        #self.filetype to it.
        self.filetype=None
        try:
            f=vorbis.VorbisFile(filename)
            self.filename=filename
            self.filetype=self.OGG
            self.tags["__filename"] = filename
            self.tags["__path"] = os.path.basename(filename)
            self.tags["__ext"] = self.filetype
            return None
        except vorbis.VorbisError:
            if eyeD3.isMp3File(filename):
                self.filename=filename
                self.filetype= self.MP3
                self.tags["__filename"] = filename
                self.tags["__path"] = os.path.basename(filename)
                self.tags["__ext"] = self.filetype
                return None
        except:
            return 1
        return 0
        
            
    def gettags(self):
        """Get the tags from self.filename, then
        sets the value of self.tags to a dictionary
        of tags in the form {tag:tag value}
        Returns 0 if failed"""
        
        self.tags={"__filename" : self.filename, 
                   "__path" : os.path.basename(self.filename),
                   "__ext" : self.filetype}
                   
        if self.filetype==self.OGG:
            f=vorbis.VorbisFile(self.filename)
            comments=f.comment().as_dict()            
            for z in comments.keys():
                self.tags[z.lower()]=comments[z][0]
            self.tags["track"]=self.tags["tracknumber"]
            del self.tags["tracknumber"]
            return self.tags
        
        elif self.filetype==self.MP3:
            #tmp has the tag with the function
            #to run when that tag is encountered.

            
            tag=eyeD3.Tag()
            if tag.link(self.filename)==0:
                return 0
            for z in tag.frames:
                if z.header.id in self.__ids:
                    try:
                        self.tags[self.__ids[z.header.id]]=z.text
                    except AttributeError:pass
            if tag.getYear() is not None:
                self.tags["date"]= tag.getYear()
            
            
            #if self.tags.has_key("track"):
                #if type (self.tags["track"]=tuple:
                    #self.tags[tags]
            #and store it in self.tags.
            #for z in tmp.keys():
                #try:
                    #if getattr(tag,tmp[z])()!=None:
                        ##FIXME: track is returned as a tuple
                        ##so for now, we only take the track number
                        #if z=="track":
                            #self.tags[z]=getattr(tag,tmp[z])()[0]
                        ##Getgenre returns a genre object, while we want
                        ##a string.
                        #elif z=="genre":
                            #self.tags[z]=getattr(tag,tmp[z])().getName()
                        #else:
                            #self.tags[z]=getattr(tag,tmp[z])()
                #except eyeD3.tag.GenreException:
                    #pass
                #except ValueError:
                    #pass
            return self.tags

        return 0
            
            
    def __setitem__(self,key,value):
        "See __getitem__"
        self.tags[key]=value
            
    def writetags(self,filename=None):
        """Writes the tags in self.tags
        to self.filename if no filename is specified"""
            
        if filename==None:
            filename=self.filename
            
        if self.filetype==self.MP3:
            
            try:   
                tag=eyeD3.Mp3AudioFile(filename).getTag()
            except eyeD3.tag.InvalidAudioFormatException:
                #Sometimes the above doesn't work
                #I really have no fucking idea why
                tag = eyeD3.Tag()
                tag.link(filename)
            
            #Set tag version to the latest.
            #I'm doing this because for some files without
            #tags the version does not want to be set
            #and this seems to work.
            try:
                tag.setVersion(eyeD3.ID3_V2_4)
            except AttributeError:
                tag = eyeD3.Tag()
                tag.link(filename)
                tag.setVersion(eyeD3.ID3_V2_4)
            try: del (self.tags["genre"])
            except KeyError: pass
            for z in self.tags:
                tag.setTextFrame(self.__revids[z],self.tags[z])
            tag.update()
            #write tags. See gettags for explanation of track
            #for z in self.tags.keys():
                #try:
                    #if z=="track":
                        #getattr(tag,tmp[z])((self.tags[z],None))
                    #else:
                        #getattr(tag,tmp[z])(self.tags[z])
                #except KeyError: pass
                
            #write other ID3 version tags, just for compatibility
            tag.update(eyeD3.ID3_V2_3)
            try:                
                tag.update(eyeD3.ID3_V1_1)
            except eyeD3.tag.GenreException:
                #This is triggered if track is in any other format
                #but an integer value.
                return 0
            
            
        if self.filetype==self.OGG:
            self.tags["tracknumber"]=self.tags["track"]
            del self.tags["track"]
            v=vorbis.VorbisComment(self.tags)
            v.write_to(self.filename)
            self.tags["track"]=self.tags["tracknumber"]
            del self.tags["tracknumber"]
