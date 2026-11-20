# SPDX-License-Identifier: GPL-3.0-or-later

"""HTTP GET for TMDB, Fanart.tv and Trakt: a timeout, one retry, and "not found" told apart
from a failure."""

import gzip
import http.client
import json
import time
import zlib
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import xbmc

from lib import log

TIMEOUT = 15  # seconds, for connecting and for each read
RETRY_PAUSE = 1.0  # seconds before the one retry
MAX_RETRY_AFTER = 30  # the longest Retry-After honoured, in seconds
_GZIP_MAGIC = b'\x1f\x8b'


class RequestFailed(Exception):
    """A request that failed after its retry, so the call it was made for can't be completed."""


def get_json(url, headers, label):
    """GET a URL and parse its JSON body, trying once more after a failure that may pass.

    :param url: the full URL, with any API key; it is never logged
    :param headers: the request headers
    :param label: what the log says for the request, such as 'TMDB GET /tv/1420'
    :return: the parsed body, or None when the server answers 404: what was asked for isn't there
    :raises RequestFailed: when the request failed, after the retry for a connection that fails,
        is reset or times out, a body cut short or unreadable, a 429 or a 5xx
    """
    for attempt in (1, 2):
        delay = RETRY_PAUSE
        try:
            with urlopen(Request(url, headers=headers), timeout=TIMEOUT) as resp:
                raw = resp.read()
                encoding = resp.headers.get('Content-Encoding', '')
            return json.loads(_decode(raw, encoding))
        except HTTPError as exc:  # before OSError, of which it is a kind
            code = exc.code
            exc.close()
            if code == 404:
                log.info('{}: not found'.format(label))
                return None
            reason = 'HTTP {}'.format(code)
            retry = code == 429 or 500 <= code <= 599
            if code == 429:
                delay = _retry_after(exc.headers)
        except (OSError, http.client.HTTPException, EOFError, zlib.error) as exc:
            # no connection, a reset, a timeout, a body cut short or a broken gzip stream
            reason = str(getattr(exc, 'reason', None) or exc) or type(exc).__name__
            retry = True
        except ValueError as exc:
            # a body that isn't JSON, such as a proxy's error page
            reason = 'unreadable reply: {}'.format(exc)
            retry = True
        if attempt == 1 and retry:
            log.info('{} failed, trying again: {}'.format(label, reason))
            if not xbmc.Monitor().waitForAbort(delay):
                continue
        log.error('{} failed: {}'.format(label, reason))
        raise RequestFailed('{} failed: {}'.format(label, reason))


def _decode(raw, encoding):
    """The body as text, ungzipped when compressed, with or without a Content-Encoding header."""
    if encoding == 'gzip' or raw[:2] == _GZIP_MAGIC:
        raw = gzip.decompress(raw)
    return raw.decode('utf-8')


def _retry_after(headers):
    """Seconds a 429 answer asks to wait, within limits."""
    try:
        return min(MAX_RETRY_AFTER, max(RETRY_PAUSE, float(headers.get('Retry-After'))))
    except (AttributeError, TypeError, ValueError):
        return RETRY_PAUSE
