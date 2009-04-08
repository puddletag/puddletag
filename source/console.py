from optparse import OptionParser
import sys,os,shutil
from puddlestuff.findfunc import *
from puddlestuff.audioinfo import Tag
from puddlestuff.console import *
import pdb

path, PATH, FILENAME = os.path, audioinfo.PATH, audioinfo.FILENAME

class PuddleError(Exception): pass

def safe_name(name, to = None):
    """Make a filename safe for use (remove some special chars)

    If any special chars are found they are replaced by to."""
    if not to:
        to = ""
    else:
        to = unicode(to)
    escaped = ""
    for ch in name:
        if ch not in r'/\*?;"|:': escaped = escaped + ch
        else: escaped = escaped + to
    if not escaped: return '""'
    return escaped

def vararg_callback(option, opt_str, value, parser):
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

def parseoptions(classes):
    parser=OptionParser()
    parser.add_option("-f","--filenames",dest="filename",action="callback",help="The filenames of the input files", callback=vararg_callback)
    parser.add_option("-p","--preview",action="store_true", dest="preview",help="Don't change anything, just print results.")
    parser.add_option("-v","--verbose",action="store_true", dest="verbose",help="Rename the directory according to your pattern.")
    #parser.add_option("-c","--continue",action="store_false", dest="cont",help="Yes, when asked.")
    for cl in classes.values():
        parser.add_option('--' + cl.command, dest='action' + cl.command, help=cl.description, action='callback', callback=vararg_callback)

    try:
        command = sys.argv[1]
    except IndexError:
        parser.print_help()
        sys.exit(0)
    (options,args)=parser.parse_args()

    actions = [{z[len('action'):]: getattr(options,z)} for z in dir(options) if z.startswith('action')]
    actions = [z for z in actions if z.values()[0] is not None]
    if not options.filename:
        print 'Dude, puddletag needs files to work on.'
        parser.print_help()
        sys.exit(0)
    return (options, actions)

class PuddleRunAction:
    name = 'RunAction'
    command = 'runaction'
    description = 'Run the specified action on the selected files.'
    usage = '--runaction Action Names'

    def setup(self, args):
        if not args:
            raise PuddleError('No Action was specified')
        temp = []
        for action in args:
            try:
                temp.extend(getActionFromName(action)[0])
            except IOError:
                raise PuddleError("The action, " + action + ", doesn't exist")
        self.funcs = temp

    def run(self, f):
        return runAction(self.funcs, f)

class Format:
    name = 'Format'
    command = 'format'
    description = 'Formats tags using a pattern'
    usage = '--format tags::pattern'

    def setup(self, tags, pattern):
        self.tags = tags
        self.pattern = pattern[0]

    def run(self, tags):
        value = tagtofilename(self.pattern, tags)
        return dict([(tag, value) for tag in self.tags])

class FileToTag:
    name = 'FileToTag'
    command = 'filetotag'
    description = 'Retrieves tag information from the filename'
    usage = 'pattern'

    def setup(self, pattern):
        self.pattern = pattern[0]

    def run(self, tags):
        return filenametotag(self.pattern, tags)


class TagToFile:
    name = 'TagToFile'
    command = 'tagtofile'
    description = 'Renames the file according to pattern'
    usage = 'pattern'

    def setup(self, pattern):
        self.pattern = pattern[0]

    def run(self, tags):
        return {'__path': tagtofilename(self.pattern, tags['__path'])}

class SetTag:
    name = 'SetTag'
    command = 'set'
    description = 'Writes the specified tags on the files.'
    usage = 'tags::values'

    def setup(self, tags, values):
        if tags:
            self.tags = tags
        else:
            raise PuddleError("No tags were specified")
        self.values = values
        if len(values) <> len(tags) and len(values) != 1:
            raise PuddleError("I can only accept one value, or values equal to the number of tags")
        elif len(values) == len(tags):
            self.tags = zip(tags, values)
        else:
            val = values[0]
            self.tags = [(tag, val) for tag in tags]

    def run(self, tags):
        return dict([(tag, value) for tag, value in self.tags])


class SetMul:
    name = 'SetMul'
    command = 'setmul'
    description = 'Writes multiple values to the specified tags'
    usage = '--setmul tags::values'

    def setup(self, tags, values):
        if tags:
            self.tags = tags
        else:
            raise PuddleError("No tags were specified")
        self.values = values
        self.tags = [(tag, values) for tag in tags]

    def run(self, tags):
        return dict([(tag, value) for tag, value in self.tags])


def pprint(tags):
    bold = chr(0x1b) + "[1m";
    normal  = chr(0x1b) + "[0m";
    red   = chr(0x1b) + "[31m";
    temp = []
    for tag, value in tags.items():
        if not isinstance(value, basestring):
            value = u'[' + ','.join(value) + u']'
        temp.append(tag + u': ' + bold + value + normal)
    return u"\n".join(temp)

def renameFile(original, tags):
    if PATH in tags:
        if path.splitext(tags[PATH])[1] == "":
            extension = path.extsep + original["__ext"]
        else:
            extension = ""
        oldfilename = original[FILENAME]
        newpath = safe_name(tags[PATH] + extension)
        newfilename = path.join(path.dirname(oldfilename), newpath)
        os.rename(oldfilename, newfilename)
        tags[FILENAME] = newfilename
        tags[PATH] = newpath
    else:
        return {}
    return tags

def writeTags(original, tags):
    try:
        renameFile(original, tags)
    except (OSError, IOError), e:
        print "Couldn't rename to " + original[FILENAME] + ": " + e.strerror
        return

    try:
        original.update(tags)
        original.save()
    except (OSError, IOError), detail:
        sys.stderr.write(u"Couldn't write to file, " + original['__filename'] + u'\n')

classes = {'runaction': PuddleRunAction, 'set': SetTag, 'setmul': SetMul}
options, actions = parseoptions(classes)
files = options.filename
identifier = QuotedString('"') | Combine(NotAny('\\') + Word(alphanums + ' !"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'))
tags = delimitedList(identifier)
commands = []
for command, args in [action.items()[0] for action in actions]:
    if len(args) != 0:
        args = u''.join(args).split(u'::')
        while True:
            try:
                args.remove(u'')
            except ValueError:
                break
        args = [tags.parseString(z).asList() for z in args]
    cl = classes[command]()
    try:
        cl.setup(*args)
    except PuddleError, e:
        print 'Error:', unicode(e)
        sys.exit(0)
    except TypeError, e:
        text = unicode(e)
        temp = []
        for s in ['takes exactly ', 'arguments (']:
            i = text.rfind(s) + len(s)
            temp.append(int(text[i:i+1]))
        if temp[0] > temp[1]:
            print 'Not enough arguments were specified to --' + cl.command
        else:
            print 'Too many arguments were specified to --' + cl.command
        print 'Usage:', cl.usage
        sys.exit(0)
    commands.append(cl.run)

for f in files:
    try:
        tag = audioinfo.Tag(f)
    except (IOError, OSError), e:
        print "Couldn't read " + f + ': ' + e.strerror
        continue
    if tag is not None:
        tags = tag.tags
        for com in commands:
            tags.update(com(tags))
        tags = audioinfo.converttag(tags)
        if options.preview:
            changes = {}
            for z in tags:
                if not (z in tag and tag[z] == tags[z]):
                    changes[z] = tags[z]
            print 'Original: \n', pprint(tag.tags), '\n'
            print 'Changes: \n', pprint(changes), '\n'
            print "Do you want to write the changes to the file? [Y/n]"
            i = raw_input()
            if i != u'n' or i != u'N':
                writeTags(tag, tags)
        elif options.verbose:
            changes = {}
            for z in tags:
                if not (z in tag and tag[z] == tags[z]):
                    changes[z] = tags[z]
            print 'Original: \n', pprint(tag.tags), '\n'
            print 'Changes: \n', pprint(changes), '\n'
            u'Now writing...' + tag['__filename']
            writeTags(tag, tags)
        else:
            writeTags(tag, tags)


#if options.preview:
    #def decor(func):
        #def s(*args):
            #x = func(*args)
            #print pprint(x)
            #return x
        #return s
    #commands = [decor(z) for z in commands]

#writefiles(commands, files)