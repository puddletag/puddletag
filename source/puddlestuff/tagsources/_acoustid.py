# This file is part of pyacoustid.
# Copyright 2012, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

import os
import json
import urllib
import urllib2
import httplib
import contextlib
try:
    import audioread
    have_audioread = True
except ImportError:
    have_audioread = False
try:
    import chromaprint
    have_chromaprint = True
except ImportError:
    have_chromaprint = False
import subprocess
import threading
import time
import gzip
from StringIO import StringIO

API_BASE_URL = 'http://api.acoustid.org/v2/'
DEFAULT_META = 'recordings'
REQUEST_INTERVAL = 0.33 # 3 requests/second.
MAX_AUDIO_LENGTH = 120 # Seconds.
FPCALC_COMMAND = 'fpcalc'
FPCALC_ENVVAR = 'FPCALC'

class AcoustidError(Exception):
    """Base for exceptions in this module."""

class FingerprintGenerationError(AcoustidError):
    """The audio could not be fingerprinted."""

class FingerprintSubmissionError(AcoustidError):
    """Missing required data for a fingerprint submission."""

class WebServiceError(AcoustidError):
    """The Web service request failed. The field ``message`` contains a
    description of the error. If this is an error that was specifically
    sent by the acoustid server, then the ``code`` field contains the
    acoustid error code.
    """
    def __init__(self, message, response=None):
        """Create an error for the given HTTP response body, if
        provided, with the ``message`` as a fallback.
        """
        if response:
            # Try to parse the JSON error response.
            try:
                data = json.loads(response)
            except ValueError:
                pass
            else:
                if isinstance(data.get('error'), dict):
                    error = data['error']
                    if 'message' in error:
                        message = error['message']
                    if 'code' in error:
                        self.code = error['code']

        super(WebServiceError, self).__init__(message)
        self.message = message

class _rate_limit(object):
    """A decorator that limits the rate at which the function may be
    called.  The rate is controlled by the REQUEST_INTERVAL module-level
    constant; set the value to zero to disable rate limiting. The
    limiting is thread-safe; only one thread may be in the function at a
    time (acts like a monitor in this sense).
    """
    def __init__(self, fun):
        self.fun = fun
        self.last_call = 0.0
        self.lock = threading.Lock()

    def __call__(self, *args, **kwargs):
        with self.lock:
            # Wait until request_rate time has passed since last_call,
            # then update last_call.
            since_last_call = time.time() - self.last_call
            if since_last_call < REQUEST_INTERVAL:
                time.sleep(REQUEST_INTERVAL - since_last_call)
            self.last_call = time.time()

            # Call the original function.
            return self.fun(*args, **kwargs)

def _compress(data):
    """Compress a string to a gzip archive."""
    sio = StringIO()
    with contextlib.closing(gzip.GzipFile(fileobj=sio, mode='wb')) as f:
        f.write(data)
    return sio.getvalue()

def _decompress(data):
    """Decompress a gzip archive contained in a string."""
    sio = StringIO(data)
    with contextlib.closing(gzip.GzipFile(fileobj=sio)) as f:
        return f.read()

def set_base_url(url):
    """Set the URL of the API server to query."""
    if not url.endswith('/'):
        url += '/'
    global API_BASE_URL
    API_BASE_URL = url

def _get_lookup_url():
    """Get the URL of the lookup API endpoint."""
    return API_BASE_URL + 'lookup'

def _get_submit_url():
    """Get the URL of the submission API endpoint."""
    return API_BASE_URL + 'submit'

@_rate_limit
def _send_request(req):
    """Given a urllib2 Request object, make the request and return a
    tuple containing the response data and headers.
    """
    try:
        with contextlib.closing(urllib2.urlopen(req)) as f:
            return f.read(), f.info()
    except urllib2.HTTPError, exc:
        raise WebServiceError('HTTP status %i' % exc.code, exc.read())
    except httplib.BadStatusLine:
        raise WebServiceError('bad HTTP status line')
    except IOError:
        raise WebServiceError('connection failed')

def _api_request(url, params):
    """Makes a POST request for the URL with the given form parameters,
    which are encoded as compressed form data, and returns a parsed JSON
    response. May raise a WebServiceError if the request fails.
    """
    body = _compress(urllib.urlencode(params))
    req = urllib2.Request(url, body, {
        'Content-Encoding': 'gzip',
        'Accept-Encoding': 'gzip',
    })

    data, headers = _send_request(req)
    if headers.get('Content-Encoding') == 'gzip':
        data = _decompress(data)

    try:
        return json.loads(data)
    except ValueError:
        raise WebServiceError('response is not valid JSON')

def fingerprint(samplerate, channels, pcmiter):
    """Fingerprint audio data given its sample rate and number of
    channels.  pcmiter should be an iterable containing blocks of PCM
    data as byte strings. Raises a FingerprintGenerationError if
    anything goes wrong.
    """
    # Maximum number of samples to decode.
    endposition = samplerate * MAX_AUDIO_LENGTH

    try:
        fper = chromaprint.Fingerprinter()
        fper.start(samplerate, channels)

        position = 0 # Samples of audio fed to the fingerprinter.
        for block in pcmiter:
            fper.feed(block)
            position += len(block) // 2 # 2 bytes/sample.
            if position >= endposition:
                break

        return fper.finish()
    except chromaprint.FingerprintError:
        raise FingerprintGenerationError("fingerprint calculation failed")

def lookup(apikey, fingerprint, duration, meta=DEFAULT_META):
    """Look up a fingerprint with the Acoustid Web service. Returns the
    Python object reflecting the response JSON data.
    """
    params = {
        'format': 'json',
        'client': apikey,
        'duration': int(duration),
        'fingerprint': fingerprint,
        'meta': meta,
    }
    return _api_request(_get_lookup_url(), params)

def parse_lookup_result(data):
    """Given a parsed JSON response, generate tuples containing the match
    score, the MusicBrainz recording ID, the title of the recording, and
    the name of the recording's first artist. (If an artist is not
    available, the last item is None.) If the response is incomplete,
    raises a WebServiceError.
    """
    if data['status'] != 'ok':
        raise WebServiceError("status: %s" % data['status'])
    if 'results' not in data:
        raise WebServiceError("results not included")

    for result in data['results']:
        score = result['score']
        if not result.get('recordings'):
            # No recording attached. This result is not very useful.
            continue
        recording = result['recordings'][0]

        # Get the artist if available.
        if recording['artists']:
            artist = recording['artists'][0]
            artist_name = artist['name']
        else:
            artist_name = None

        yield score, recording['id'], recording['title'], artist_name

def _fingerprint_file_audioread(path):
    """Fingerprint a file by using audioread and chromaprint."""
    try:
        with audioread.audio_open(path) as f:
            duration = f.duration
            fp = fingerprint(f.samplerate, f.channels, iter(f))
    except audioread.DecodeError:
        raise FingerprintGenerationError("audio could not be decoded")
    return duration, fp

def _fingerprint_file_fpcalc(path):
    """Fingerprint a file by calling the fpcalc application."""
    fpcalc = os.environ.get(FPCALC_ENVVAR, FPCALC_COMMAND)
    command = [fpcalc, "-length", str(MAX_AUDIO_LENGTH), path]
    try:
        output = subprocess.check_output(command)
    except (OSError, subprocess.CalledProcessError):
        raise FingerprintGenerationError("fpcalc invocation failed")

    duration = fp = None
    for line in output.splitlines():
        try:
            parts = line.split('=', 1)
        except ValueError:
            raise FingerprintGenerationError("malformed fpcalc output")
        if parts[0] == 'DURATION':
            try:
                duration = int(parts[1])
            except ValueError:
                raise FingerprintGenerationError("fpcalc duration not numeric")
        elif parts[0] == 'FINGERPRINT':
            fp = parts[1]

    if duration is None or fp is None:
        raise FingerprintGenerationError("missing fpcalc output")
    return duration, fp

def match(apikey, path, meta=DEFAULT_META, parse=True):
    """Look up the metadata for an audio file. If ``parse`` is true,
    then ``parse_lookup_result`` is used to return an iterator over
    small tuple of relevant information; otherwise, the full parsed JSON
    response is returned.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if have_audioread and have_chromaprint:
        duration, fp = _fingerprint_file_audioread(path)
    else:
        duration, fp = _fingerprint_file_fpcalc(path)
    response = lookup(apikey, fp, duration, meta)
    if parse:
        return parse_lookup_result(response)
    else:
        return response

def submit(apikey, userkey, data):
    """Submit a fingerprint to the acoustid server. The ``apikey`` and
    ``userkey`` parameters are API keys for the application and the
    submitting user, respectively.

    ``data`` may be either a single dictionary or a list of
    dictionaries. In either case, each dictionary must contain a
    ``fingerprint`` key and a ``duration`` key and may include the
    following: ``puid``, ``mbid``, ``track``, ``artist``, ``album``,
    ``albumartist``, ``year``, ``trackno``, ``discno``, ``fileformat``,
    ``bitrate``

    If the required keys are not present in a dictionary, a
    FingerprintSubmissionError is raised.
    """
    if isinstance(data, dict):
        data = [data]

    args = {
        'format': 'json',
        'client': apikey,
        'user': userkey,
    }

    # Build up "field.#" parameters corresponding to the parameters
    # given in each dictionary.
    for i, d in enumerate(data):
        if "duration" not in d or "fingerprint" not in d:
            raise FingerprintSubmissionError("missing required parameters")
        for k, v in d.iteritems():
            args["%s.%s" % (k, i)] = v

    response = _api_request(_get_submit_url(), args)
    if response['status'] != 'ok':
        raise WebServiceError("status: %s" % data['status'])
