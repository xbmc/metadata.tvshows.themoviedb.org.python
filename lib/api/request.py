# SPDX-License-Identifier: GPL-3.0-or-later

"""HTTP GET for TMDB, Fanart.tv and Trakt, trying once more after a failure that may pass."""

import gzip
import http.client
import io
import json
import select
import ssl
import threading
import time
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, getproxies, proxy_bypass, urlopen

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
            raw, encoding = SESSION.send(Request(url, headers=headers), _TIMEOUT)
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
    """Seconds a 429 asks to wait, between the usual pause and the cap. Retry-After is a number
    of seconds or an HTTP date (RFC 9110, 10.2.3)."""
    value = headers.get('Retry-After') if headers else None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except (TypeError, ValueError, OverflowError, OSError):
            return _RETRY_PAUSE
    return min(_MAX_RETRY_AFTER, max(_RETRY_PAUSE, seconds))


# One connection kept open to each site, for all the calls Kodi makes in the interpreter it runs
# the add-on in again, rather than a new connection, and its TLS handshake, for each request
# How a kept connection the server has closed meanwhile shows when it is used
_CLOSED = (http.client.RemoteDisconnected, http.client.BadStatusLine,
           http.client.CannotSendRequest, ConnectionResetError, ConnectionAbortedError,
           BrokenPipeError, ssl.SSLEOFError, ssl.SSLZeroReturnError)


class Session(object):
    """The connections kept open, one to each site. Kodi runs the add-on's calls in an interpreter
    it keeps for them (reuselanguageinvoker), so one instance, SESSION, serves them all."""

    def __init__(self):
        self._connections = {}  # (scheme, host, port) -> connection
        self._lock = threading.Lock()
        self._ssl_context = None
        self._proxies = None

    def send(self, req, timeout):
        """The body of a request's answer and its Content-Encoding, on the connection kept open
        to its site. An error status raises HTTPError, as urlopen() does."""
        parts = urlsplit(req.full_url)
        scheme, host = parts.scheme.lower(), parts.hostname
        if scheme not in ('http', 'https') or not host or self._proxied(scheme, host):
            return _send_urlopen(req, timeout)
        key = (scheme, host, parts.port)
        target = (parts.path or '/') + ('?' + parts.query if parts.query else '')
        headers = dict(req.header_items())
        for fresh in (False, True):
            conn = None if fresh else self._kept_connection(key, timeout)
            reused = conn is not None
            if conn is None:
                conn = self._new_connection(scheme, host, parts.port, timeout)
            try:
                conn.request(req.get_method(), target, body=req.data, headers=headers)
                response = conn.getresponse()
            except _CLOSED:
                conn.close()
                if reused:
                    # The server closed it while it was kept: sent again on a new connection,
                    # which isn't the request's one retry
                    continue
                raise
            except BaseException:
                conn.close()
                raise
            if response.status >= 400:
                # The status comes with the headers, whatever the body does after them. Only a
                # connection with no body to drain is kept.
                if response.length == 0 and not response.will_close:
                    response.close()
                    self._keep(key, conn)
                else:
                    response.close()
                    conn.close()
                raise HTTPError(req.full_url, response.status, response.reason,
                                response.headers, io.BytesIO(b''))
            try:
                raw = response.read()
            except BaseException:
                conn.close()
                raise
            if response.will_close:
                conn.close()
            else:
                self._keep(key, conn)
            if 300 <= response.status < 400 and response.status != 304:
                # A redirect, which urlopen() follows
                return _send_urlopen(req, timeout)
            return raw, response.headers.get('Content-Encoding')

    def close(self):
        """Closes every connection kept open"""
        with self._lock:
            kept_now = list(self._connections.values())
            self._connections.clear()
        for conn in kept_now:
            conn.close()

    def _kept_connection(self, key, timeout):
        """The connection kept open to a site, unless the server has closed it meanwhile"""
        with self._lock:
            conn = self._connections.pop(key, None)
        if conn is None:
            return None
        # Readable while no answer is awaited: the server has closed it
        try:
            closed = conn.sock is None or bool(select.select([conn.sock], [], [], 0)[0])
        except (OSError, ValueError):
            closed = True
        if closed:
            conn.close()
            return None
        conn.timeout = timeout
        conn.sock.settimeout(timeout)
        return conn

    def _keep(self, key, conn):
        with self._lock:
            other = self._connections.pop(key, None)
            self._connections[key] = conn
        if other is not None:
            other.close()

    def _new_connection(self, scheme, host, port, timeout):
        if scheme == 'https':
            if self._ssl_context is None:
                self._ssl_context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, port, timeout=timeout,
                                               context=self._ssl_context)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        try:
            conn.connect()
        except BaseException:
            conn.close()
            raise
        return conn

    def _proxied(self, scheme, host):
        """True when the system has a proxy for the site, which urlopen() goes through"""
        if self._proxies is None:
            self._proxies = getproxies()
        return scheme in self._proxies and not proxy_bypass(host)


def _send_urlopen(req, timeout):
    with urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get('Content-Encoding')


# The one session, for all the add-on's calls in an interpreter
SESSION = Session()
