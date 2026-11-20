# SPDX-License-Identifier: GPL-3.0-or-later

"""IMDb ratings from script.module.imdbratings.

The module keeps one store of IMDb's ratings dataset (title.ratings.tsv.gz), shared by every
add-on and interpreter that uses it, and updated by one of them at a time. It checks IMDb for a
newer dataset itself, at most every 15 minutes, and after a failed download waits 6 hours.
"""

import os
import time

import imdbratings
import xbmc
import xbmcvfs

from lib import log
from lib.api.request import RequestFailed
from lib.config import ADDON

# Seconds a call waits for another interpreter's first load of the dataset
FIRST_LOAD_WAIT = 60

_old_store_checked = False


def get_rating(imdb_id):
    """Lookup IMDb rating. Returns (rating, votes), or None when the dataset has none for the id.

    Raises RequestFailed when there is no dataset to look in: the store can't be read, or no
    dataset has been loaded yet and none could be. imdbratings.get_rating() returns None for
    that too; dataset_date() tells the two apart, as it is None only before a first load or
    when the store can't be read.
    """
    if not imdb_id:
        return None
    _remove_old_store()
    rating = imdbratings.get_rating(imdb_id)
    if rating is not None or imdbratings.dataset_date() is not None:
        return rating
    _wait_for_first_load()
    rating = imdbratings.get_rating(imdb_id)
    if rating is None and imdbratings.dataset_date() is None:
        raise RequestFailed('IMDb ratings: no dataset loaded, and none could be')
    return rating


def _wait_for_first_load():
    """Wait, within limits, for a first load of the dataset that another interpreter is making.

    refresh() takes the store's lock, waiting up to 5 s while another interpreter holds it to
    load the dataset, and loads the dataset itself when a check is due. When it returns at once,
    the lock was free and no check was due: nothing is loading, and waiting longer won't help.
    """
    monitor = xbmc.Monitor()
    deadline = time.monotonic() + FIRST_LOAD_WAIT
    while time.monotonic() < deadline and not monitor.abortRequested():
        started = time.monotonic()
        imdbratings.refresh()
        if imdbratings.dataset_date() is not None or time.monotonic() - started < 1:
            return


def _remove_old_store():
    """Remove the add-on's own copy of the dataset, which the module's store replaces."""
    global _old_store_checked
    if _old_store_checked:
        return
    _old_store_checked = True
    profile = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    for name in ('imdb_ratings.db', 'imdb_ratings.db.tmp'):
        path = os.path.join(profile, name)
        if os.path.exists(path):
            try:
                os.remove(path)
                log.info('removed the old IMDb ratings cache {}'.format(name))
            except OSError as exc:
                # still open somewhere: try again on the next call
                _old_store_checked = False
                log.debug('old IMDb ratings cache {} not removed: {}'.format(name, exc))
