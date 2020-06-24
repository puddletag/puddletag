# -*- coding: utf-8 -*-
"""Usage python get_tag.py filename | dirname"""
import os
import pickle
import sys

import mutagen

if len(sys.argv) < 3:
    print("""Usage: python get_tag.py filename|dirname output""")
    sys.exit()

filename = sys.argv[1]
output_fn = sys.argv[2]
tags = []
if os.path.isdir(filename):
    files = os.listdir(filename)
    for f in files:
        try:
            tags.append(mutagen.File(os.path.join(filename, f)))
        except Exception as e:
            print('Error loading file %s: %s' % (f, str(e)))
else:
    tags.append(mutagen.File(filename))

output = open(output_fn, 'wb')
pickle.dump(tags, output)
output.close()
print('Tags stored in %s' % output_fn)
