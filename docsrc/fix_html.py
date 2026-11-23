import os
import re
import sys


def remove_h1(text):
    regexp = r"<h1.*?>[a-zA-Z \n]*</h1>"
    return re.sub(regexp, '', text)


def clean_files(dirpath):
    filenames = set(['index.html', 'screenshots.html', 'about.html'])
    for filename in filenames:
        path = os.path.join(dirpath, filename)
        if not path.endswith('.html'):
            continue
        try:
            with open(path, 'r+') as f:
                print("Fixing: " + path)
                text = f.read()
                text = remove_h1(text)
                f.seek(0)
                f.write(text)
                f.truncate()
        except (IOError, OSError):
            print("Could not edit: " + path)


if __name__ == "__main__":
    input_dir = sys.argv[1]
    clean_files(input_dir)
