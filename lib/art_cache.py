# SPDX-License-Identifier: GPL-3.0-or-later

"""SQLite disk cache for artwork data between getdetails and getartwork."""

import json
import os
import sqlite3

import xbmcvfs

from lib import log
from lib.config import ADDON

_db_path = ''
_initialized = False


def _reset_initialized():
    """Force table re-creation on next _open() call."""
    global _initialized
    _initialized = False


def _open():
    """Open a connection, initializing the DB on first use."""
    global _db_path, _initialized

    if not _db_path:
        addon_data = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
        if not os.path.exists(addon_data):
            os.makedirs(addon_data)
        _db_path = os.path.join(addon_data, 'art_cache.db')

    try:
        conn = sqlite3.connect(_db_path)
        if not _initialized:
            conn.execute('DROP TABLE IF EXISTS art_cache')
            conn.execute(
                'CREATE TABLE art_cache '
                '(tmdb_id TEXT PRIMARY KEY, data TEXT)'
            )
            conn.commit()
            _initialized = True
        return conn
    except sqlite3.Error as exc:
        log.error('art_cache open failed: {}'.format(exc))
        return None


def store(tmdb_id, show):
    """Write stripped artwork data for a show after fanart.tv merge."""
    stripped = {
        'name': show.get('name', ''),
        'images': show.get('images', {}),
        'seasons': [
            {
                'season_number': s.get('season_number', 0),
                'images': s.get('images', {}),
            }
            for s in show.get('seasons', []) if s.get('images')
        ],
    }
    conn = _open()
    if not conn:
        return
    try:
        conn.execute(
            'INSERT OR REPLACE INTO art_cache (tmdb_id, data) '
            'VALUES (?, ?)',
            (str(tmdb_id), json.dumps(stripped, separators=(',', ':'))),
        )
        conn.commit()
    except sqlite3.Error as exc:
        _reset_initialized()
        log.error('art_cache store failed: {}'.format(exc))
    finally:
        conn.close()


def load(tmdb_id):
    """Read artwork data for a show. Returns stripped dict or None."""
    conn = _open()
    if not conn:
        return None
    try:
        row = conn.execute(
            'SELECT data FROM art_cache WHERE tmdb_id = ?',
            (str(tmdb_id),),
        ).fetchone()
        if row:
            return json.loads(row[0])
    except (sqlite3.Error, ValueError) as exc:
        _reset_initialized()
        log.error('art_cache load failed: {}'.format(exc))
    finally:
        conn.close()
    return None


def clear():
    """Wipe all entries. Called when getartwork batch ends."""
    conn = _open()
    if not conn:
        return
    try:
        deleted = conn.execute('DELETE FROM art_cache').rowcount
        conn.commit()
        if deleted:
            log.debug('art_cache: cleared {} entries'.format(deleted))
    except sqlite3.Error as exc:
        log.error('art_cache clear failed: {}'.format(exc))
    finally:
        conn.close()
