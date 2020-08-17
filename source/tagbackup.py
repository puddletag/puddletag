"""Routines and script to back up audio metadata (puddletag
audioinfo.Tag objects).

Data is stored as json."""
import json
import logging
import os
from optparse import OptionParser

from puddlestuff import audioinfo
from puddlestuff.audioinfo import tag_to_json, b64_to_img


def tags_to_json(dirpath, fields=None):
    ret = []
    for fn in os.listdir(dirpath):
        fn = os.path.join(dirpath, fn)
        if os.path.isdir(fn):
            ret.extend(tags_to_json(fn, fields))
            continue
        tag = tag_to_json(fn, fields)
        if tag:
            ret.append(tag)
    return ret


def backup_dir(dirpath, fn, fields=None):
    fo = open(fn, 'w')
    fo.write(json.dumps(tags_to_json(dirpath, fields)))
    fo.close()


def main():
    usage = "Usage: %prog [-f FIELDS] [-b dirpath | -r] filename"
    parser = OptionParser(usage=usage)

    parser.add_option("-b", "--backup", dest="backup",
                      default='',
                      help="Backs up all audio tags in dirpath to filename.",
                      metavar="BACKUP")
    parser.add_option("-r", "--restore", dest="restore",
                      default='',
                      help="Restores audio tags found in filename.",
                      metavar="RESTORE", action="store_true")
    parser.add_option("-f", "--fields", dest="fields",
                      default='',
                      help="Comma separated list of fields. "
                           "Backed up data will be restricted to this list, but if "
                           "restored will overwrite the complete file.",
                      metavar="FIELDS", action='store')

    options, filenames = parser.parse_args()
    if not (options.backup or options.restore):
        "Backs ups and restores audio metadata in directories."
        parser.print_help()
        exit()

    if not filenames:
        logging.debug("Fatal Error: Require filename to write backup to!")
        exit(1)

    filename = filenames[0]

    if os.path.exists(filename) and options.backup:
        logging.debug('Fatal Error: Backup file %s already exists', filename)
        exit(2)

    fields = options.fields if options.fields else None
    if fields:
        fields = [z.strip() for z in fields.split(',')]

    if options.backup:
        backup_dir(options.backup, filename, fields)
    elif options.restore:
        restore_backup(filename)


def restore_backup(fn):
    for i, tag in enumerate(json.loads(open(fn, 'r').read())):
        try:
            fn = tag['__path']
        except KeyError:
            'Error: A file was backed up without a file path.'
        try:
            audio = audioinfo.Tag(fn)
        except EnvironmentError as e:
            "Error: Couldn't restore", fn, str(e)
            continue
        except Exception as e:
            "Error: Couldn't restore", fn, str(e)
            continue

        if '__image' in tag:
            images = tag['__image']
            del (tag['__image'])
            audio.images = list(map(b64_to_img, images))

        audio.clear()
        audio.update(tag)
        audio.save()


if __name__ == '__main__':
    main()
