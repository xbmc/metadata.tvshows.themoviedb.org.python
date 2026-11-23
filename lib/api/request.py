# SPDX-License-Identifier: GPL-3.0-or-later

"""HTTP GET for TMDB, Fanart.tv and Trakt, trying once more after a failure that may pass."""

import gzip
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import xbmc

from lib import log

_TIMEOUT = 15
_RETRY_PAUSE = 1
# Kodi waits on a scraper call without a time limit
_MAX_RETRY_AFTER = 10
_GZIP_MAGIC = b'\x1f\x8b'


class RequestFailed(Exception):
    """A request that still failed after its retry. Unlike a 404, it doesn't tell that what was
    asked for isn't there."""


def get_json(url, headers, label):
    """GET parsed JSON, or None for a 404; retries once, except a 4xx other than 429.

    Raises RequestFailed when the request still fails.
    """
    for attempt in (1, 2):
        try:
            with urlopen(Request(url, headers=headers), timeout=_TIMEOUT) as resp:
                raw = resp.read()
                encoding = resp.headers.get('Content-Encoding')
            return json.loads(_decode(raw, encoding))
        except HTTPError as exc:
            exc.close()
            if exc.code == 404:
                log.info('{}: not found'.format(label))
                return None
            reason = 'HTTP {}'.format(exc.code)
            retry = exc.code == 429 or exc.code >= 500
            pause = _retry_after(exc.headers) if exc.code == 429 else _RETRY_PAUSE
        except Exception as exc:
            reason = str(exc) or type(exc).__name__
            retry = True
            pause = _RETRY_PAUSE
        if attempt == 1 and retry:
            log.info('{} failed, trying again: {}'.format(label, reason))
            if not xbmc.Monitor().waitForAbort(pause):
                continue
        log.error('{} failed: {}'.format(label, reason))
        raise RequestFailed('{} failed: {}'.format(label, reason))


def _decode(raw, encoding):
    """Decode the body, ungzipped when compressed, with or without the header saying so."""
    if encoding == 'gzip' or raw[:2] == _GZIP_MAGIC:
        raw = gzip.decompress(raw)
    return raw.decode('utf-8')


def _retry_after(headers):
    """Seconds a 429 asks to wait, between the usual pause and the cap."""
    try:
        return min(_MAX_RETRY_AFTER, max(_RETRY_PAUSE, float(headers.get('Retry-After'))))
    except (TypeError, ValueError):
        return _RETRY_PAUSE
