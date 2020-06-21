from mutagen.id3 import TCON

GENRES = sorted(TCON.GENRES)

DIRNAME = '__dirname'
DIRPATH = '__dirpath'
EXTENSION = '__ext'
FILENAME = "__filename"
FILENAME_NO_EXT = '__filename_no_ext'
IMAGE_FIELD = '__image'
IMAGE_MIMETYPE = '__image_mimetype'
IMAGE_TYPE_FIELD = '__image_type'
NUM_IMAGES = '__num_images'
PARENT_DIR = '__parent_dir'
PATH = "__path"

MONO = 'Mono'
JOINT_STEREO = 'Joint-Stereo'
DUAL_CHANNEL = 'Dual-Channel'
STEREO = 'Stereo'

MIMETYPE = 'mime'
DESCRIPTION = 'description'
DATA = 'data'
IMAGETYPE = 'imagetype'

DEFAULT_COVER = 3

FIELDS = [
    'album', 'albumsortorder', 'arranger', 'artist', 'audiodelay',
    'audiolength', 'audiosize', 'author', 'bpm', 'comment', 'composer',
    'conductor', 'copyright', 'date', 'discnumber', 'encodedby',
    'encodingsettings', 'encodingtime', 'filename', 'fileowner', 'filetype',
    'genre', 'grouping', 'initialkey', 'involvedpeople', 'isrc',
    'itunesalbumsortorder', 'itunescompilationflag', 'itunescomposersortorder',
    'language', 'lyricist', 'mediatype', 'mood', 'musiciancredits',
    'organization', 'originalalbum', 'originalartist', 'originalreleasetime',
    'originalyear', 'performersortorder', 'performer', 'popularimeter',
    'producednotice', 'radioowner', 'radiostationname', 'recordingdates',
    'releasetime', 'setsubtitle', 'taggingtime', 'time', 'title',
    'titlesortorder', 'track', 'ufid', 'version', 'wwwartist',
    'wwwcommercialinfo', 'wwwcopyright', 'wwwfileinfo', 'wwwpayment',
    'wwwpublisher', 'wwwradio', 'wwwsource', 'year']

FILETAGS = [PATH, FILENAME, EXTENSION, DIRPATH, DIRNAME, FILENAME_NO_EXT,
            PARENT_DIR]

FILE_FIELDS = FILETAGS

IMAGETAGS = (MIMETYPE, DESCRIPTION, DATA, IMAGETYPE)

IMAGETYPES = ['Other', 'File Icon', 'Other File Icon', 'Cover (Front)',
              'Cover (Back)', 'Leaflet page', 'Media (e.g. label side of CD)',
              'Lead artist', 'Artist', 'Conductor', 'Band', 'Composer', 'Lyricist',
              'Recording Location', 'During recording', 'During performance',
              'Movie/video screen capture', 'A bright coloured fish', 'Illustration',
              'Band/artist logotype', 'Publisher/Studio logotype']

MODES = [STEREO, JOINT_STEREO, DUAL_CHANNEL, MONO]

READONLY = (PARENT_DIR, IMAGE_MIMETYPE, IMAGE_TYPE_FIELD, NUM_IMAGES,
            '__accessed', '__app',
            '__albumgain', '__bitrate', '__channels', "__cover_mimetype",
            "__cover_size", "__covers", "__created", '__file_access_date',
            '__file_access_datetime', '__file_access_datetime_raw',
            "__file_create_date", "__file_create_datetime",
            "__file_create_datetime_raw", "__file_mod_date",
            "__file_mod_datetime", "__file_mod_datetime_raw", "__file_size",
            "__file_size_bytes", "__file_size_kb", "__file_size_mb",
            '__filetype', '__frequency', '__layer', "__length",
            "__length_seconds", "__library", "__mode", "__modified",
            "__parent_dir", "__size", "__tag", "__tag_read", '__titlegain',
            "__total", '__version')

INFOTAGS = FILETAGS + list(READONLY)

TEXT_FIELDS = ['album', 'albumartist', 'albumsortorder', 'arranger',
               'artist', 'audiodelay', 'audiolength', 'audiosize', 'author',
               'bpm', 'composer', 'conductor', 'copyright', 'date', 'discnumber',
               'encodedby', 'encodingsettings', 'filename', 'fileowner',
               'filetype', 'grouping', 'initialkey', 'isrc', 'itunesalbumsortorder',
               'itunescompilationflag', 'itunescomposersortorder', 'language',
               'lyricist', 'mediatype', 'mood', 'organization', 'originalalbum',
               'originalartist', 'originalyear', 'peformersortorder', 'producednotice',
               'radioowner', 'radiostationname', 'recordingdates', 'setsubtitle',
               'time', 'title', 'titlesortorder', 'track', 'version', 'year']
