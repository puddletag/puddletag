"""Routines and script to back up audio metadata (puddletag
audioinfo.Tag objects).

Data is stored as json."""
import base64, json, os, sys, traceback

from optparse import OptionParser

from puddlestuff import audioinfo
from puddlestuff.audioinfo import tag_to_json
    
def tags_to_json(dirpath):
    ret = []
    for fn in os.listdir(dirpath):
        fn = os.path.join(dirpath, fn)
        if os.path.isdir(fn):
            ret.extend(tags_to_json(fn))
            return
        tag = tag_to_json(fn)
        if tag:
            ret.append(tag)
    return ret

def backup_dir(dirpath, fn):
    fo = open(fn, 'w')
    fo.write(json.dumps(tags_to_json(dirpath)))
    fo.close()

def main():
    usage = "Usage: %prog [-b dirpath | -r] filename"
    parser = OptionParser(usage=usage)

    parser.add_option("-b", "--backup", dest="backup",
        default='',
        help="Backs up all audio tags in dirpath to filename.",
        metavar="BACKUP")
    parser.add_option("-r", "--restore", dest="restore",
        default='',
        help="Restores audio tags found in filename.",
        metavar="RESTORE", action="store_true")

    options, filenames = parser.parse_args()
    if not (options.backup or options.restore):
        "Backs ups and restores audio metadata in directories."
        parser.print_help()
        exit()

    if not filenames:
        print "Fatal Error: Require filename to write backup to!"
        exit(1)

    filename = filenames[0]

    if os.path.exists(filename) and options.backup:
        print 'Fatal Error: Backup file,', filename, 'already exists!'
        exit(2)

    if options.backup:
        backup_dir(options.backup, filename)
    elif options.restore:
        restore_backup(filename)

def restore_backup(fn):
    
    for i, tag in enumerate(json.loads(open(fn, 'r').read())):
        fn = tag['__path']
        try:
            audio = audioinfo.Tag(fn)
        except EnvironmentError, e:
            "Error: Couldn't restore", fn, str(e)
            continue
        except Exception, e:
            "Error: Couldn't restore", fn, str(e)
            continue

        if '__image' in tag:
            images = tag['__image']
            del(tag['__image'])
            audio.images = map(b64_to_img, images)

        audio.clear()
        audio.update(tag)
        audio.save()

if __name__ == '__main__':
    main()