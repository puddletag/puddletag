# -*- coding: utf-8 -*-
import sys
import cStringIO
mode_to_bpp = {'1':1, 'L':8, 'P':8, 'RGB':24, 'RGBA':32, 'CMYK':32, 'YCbCr':24, 'I':32, 'F':32}

MIMES = {'PNG': 'image/png',
         'JPEG': 'image/jpeg',
         'GIF': 'image/gif'}

imageproperties = None
image_size = None

try:
    from PyQt4.QtGui import QImage

    def imageproperties(filename = None, fp = None, data = None):
        assert filename or fp or data
        if filename:
            data = open(filename, 'rb').read()
        elif fp:
            fp.seek(0)
            data = fp.read()

        height, width = QImage.fromData(data).size()

        return {'size': pic.size, 'depth': image.depth()}

    image_size = lambda *args, **kwargs: imageproperties(*args, **kwargs)['size']

except ImportError:
    pass

try:
    import Image

    def imageproperties(filename = None, fp = None, data = None):
        assert filename or fp or data
        if filename:
            pic = Image.open(filename)
            data = open(filename, 'rb').read()
        elif fp:
            data = fp.read()
            fp.seek(0)
            pic = Image.open(fp)
        elif data:
            pic = Image.open(cStringIO.StringIO(data))
        colors = pic.getcolors()
        colors = len(colors) if colors else 0

        return  {'format': pic.format, 'size': pic.size, 'mode': pic.mode,
                'depth': mode_to_bpp[pic.mode], 'mime': MIMES[pic.format],
                'data': data, 'colors': colors}

    image_size = lambda *args, **kwargs: imageproperties(*args, **kwargs)['size']

except ImportError:
    pass