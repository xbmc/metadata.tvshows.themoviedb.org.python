# SPDX-License-Identifier: GPL-3.0-or-later

"""IMDb ratings from script.module.imdbratings.

The module keeps one store of IMDb's ratings dataset (title.ratings.tsv.gz), shared by every
add-on and interpreter that uses it, and updated by one of them at a time. It checks IMDb for a
newer dataset itself, makes the first load, and waits for another add-on's.
"""

import os

import imdbratings
import xbmcvfs

from lib import log
from lib.api.request import RequestFailed
from lib.config import ADDON

_old_store_checked = False


def get_rating(imdb_id):
    """Lookup IMDb rating. Returns (rating, votes), or None when the dataset has none for the id.

    Raises RequestFailed when there is no dataset to look in: the store can't be read, or no
    dataset has been loaded yet. imdbratings.get_rating() returns None for that too;
    dataset_date() tells the two apart, as it is None only before a first load or when the store
    can't be read.
    """
    if not imdb_id:
        return None
    _remove_old_store()
    # dataset_date() is read before the rating: a first load that ends between the two reads
    # would otherwise pass for a show or episode without a rating
    loaded = imdbratings.dataset_date() is not None
    rating = imdbratings.get_rating(imdb_id)
    if rating is not None or loaded:
        return rating
    # No dataset before the read: one loaded meanwhile, by this call or another add-on, is read
    # again; still none, there is nothing to look in
    if imdbratings.dataset_date() is not None:
        return imdbratings.get_rating(imdb_id)
    raise RequestFailed('IMDb ratings: no dataset loaded')


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
