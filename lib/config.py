# SPDX-License-Identifier: GPL-3.0-or-later

"""Addon settings loader with per-source path override support."""

import json
import sys
from urllib.parse import parse_qsl

from xbmcaddon import Addon

ADDON = Addon()

API_HEADERS = {
    'User-Agent': ADDON.getAddonInfo('id'),
    'Accept': 'application/json',
}

TMDB_API_KEY = '0142a22c560ce3efb1cfd6f3b2faab77'

TRAKT_CLIENTID = '5e427c3175ad07ecc2e6b28fac93c3170cb0d7f8bd4d287e94629ed12b7daa78'

FANARTTV_BASE = 'https://webservice.fanart.tv/v3.2'
FANARTTV_KEY = '389a849af448f000eb6b0e223ffe84ac'

_cache_limit = 0


def get_cache_limit():
    """Max cached shows, sized to available RAM. Computed once on first use."""
    global _cache_limit
    if _cache_limit:
        return _cache_limit
    try:
        import xbmc as _xbmc
        free_mb = _xbmc.getFreeMem()
    except Exception:
        free_mb = 1024
    # ~150KB per cached show; scale with available RAM
    _cache_limit = max(10, free_mb // 2)
    from lib import log as _log
    _log.debug('cache limit: {} shows ({}MB free)'.format(_cache_limit, free_mb))
    return _cache_limit


FANARTTV_MAPPING = {
    'showbackground': 'backdrops',
    'tvposter': 'posters',
    'tvbanner': 'banner',
    'hdtvlogo': 'clearlogo',
    'clearlogo': 'clearlogo',
    'hdclearart': 'clearart',
    'clearart': 'clearart',
    'tvthumb': 'landscape',
    'characterart': 'characterart',
    'seasonposter': 'season_posters',
    'seasonbanner': 'season_banner',
    'seasonthumb': 'season_landscape',
}


def get_settings(params=None):
    path = _path_settings(params)

    def _str(key, default=''):
        return path.get(key, ADDON.getSetting(key)) or default

    def _bool(key, default=False):
        val = path.get(key)
        if val is not None:
            return bool(val)
        try:
            return ADDON.getSettingBool(key)
        except RuntimeError:
            return default

    lang_details = _str('languageDetails', 'en-US')
    if _bool('usedifferentlangforimages'):
        lang_images = _str('languageImages', 'en-US')
    else:
        lang_images = lang_details

    use_prefix = _bool('usecertprefix', True)

    return {
        'lang_details': lang_details,
        'lang_images': lang_images,
        'cert_country': _str('tmdbcertcountry', 'us'),
        'use_cert_prefix': use_prefix,
        'cert_prefix': _str('certprefix', 'Rated ') if use_prefix else '',
        'keep_original_title': _bool('keeporiginaltitle'),
        'keywords_as_tags': _bool('keywordsastags', True),
        'cat_landscape': _bool('cat_landscape', True),
        'cat_keyart': _bool('cat_keyart', True),
        'prefer_maxres': _bool('art_prefer_maxres'),
        'studio_country': _bool('studio_country'),
        'enable_trailer': _bool('enab_trailer', True),
        'trailer_player': _str('players_opt', 'Tubed'),
        'default_rating': _str('ratings', 'TMDb'),
        'imdb_anyway': _bool('imdbanyway'),
        'trakt_anyway': _bool('traktanyway'),
        'tmdb_anyway': _bool('tmdbanyway', True),
        'enable_fanarttv': _bool('enable_fanarttv', True),
        'fanarttv_clientkey': _str('fanarttv_clientkey'),
        'verbose_log': _bool('verboselog'),
    }


def _path_settings(params=None):
    """Extract per-source path settings from params or query string."""
    try:
        if params is None:
            params = dict(parse_qsl(sys.argv[2].lstrip('?')))
        return json.loads(params.get('pathSettings', '{}'))
    except (IndexError, ValueError, TypeError):
        return {}
