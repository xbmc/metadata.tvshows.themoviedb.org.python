# SPDX-License-Identifier: GPL-3.0-or-later

"""TMDB API v3 client."""

import time
from collections import OrderedDict
from urllib.parse import urlencode

from lib import log
from lib.api.request import RequestFailed, get_json
from lib.config import API_HEADERS, CACHE_LIMIT, TMDB_API_KEY

_BASE = 'https://api.themoviedb.org/3'
# season appends repeat the whole show payload
_HEADERS = dict(API_HEADERS, **{'Accept-Encoding': 'gzip'})
# TMDB rejects more than 20 appends
_MAX_APPENDS = 20
# soaps credit hundreds, aggregate fallback thousands
_MAX_CAST = 200
# {show_id: {'show': dict, 'episodes': {(s,e): dict}, 'used': time}}
# 'episodes' is only ever a show's whole guide
_cache = OrderedDict()
# shows whose episodes an interpreter keeps, and seconds it keeps them unused. Kodi's reworked
# video scanner looks up to 8 shows ahead of the one it adds (16 when so set), each listing its
# episodes before the scan asks for those of the show before it: more than that are kept.
_EPISODES_KEPT = 20
_EPISODES_TTL = 15 * 60
_img_base = ''


def get_image_base():
    """Image base URL from /configuration, fetched once per session."""
    global _img_base
    if not _img_base:
        url = '{}{}?{}'.format(_BASE, '/configuration',
                               urlencode({'api_key': TMDB_API_KEY}))
        try:
            data = get_json(url, _HEADERS, 'TMDB GET /configuration') or {}
        except RequestFailed:
            # TMDB's documented base below loses nothing, so the call goes on
            data = {}
        _img_base = ((data.get('images') or {}).get('secure_base_url')
                     or 'https://image.tmdb.org/t/p/')
        log.debug('TMDB image base: {}'.format(_img_base))
    return _img_base


def _touch(show_id):
    """Mark a cached show used now, and the most recently used."""
    entry = _cache.get(show_id)
    if entry is not None:
        entry['used'] = time.time()
        _cache.move_to_end(show_id)


def evict_episodes():
    """Drop the episodes of shows unused for a while, and of all but the most recently used.

    Shows are evicted by age and count, not when another show's details are asked for: Kodi can
    run a show's calls on any of several interpreters, each with its own cache.
    """
    now = time.time()
    with_episodes = [show_id for show_id, entry in _cache.items() if 'episodes' in entry]
    for i, show_id in enumerate(reversed(with_episodes)):
        entry = _cache[show_id]
        if i >= _EPISODES_KEPT or now - entry.get('used', 0) > _EPISODES_TTL:
            del entry['episodes']
            log.debug('cache evict episodes of show {}'.format(show_id))


def _left_out(what, exc):
    """Log a part of a show's details left out because its request failed, after the retry"""
    log.info('{} left out: {}'.format(what, exc))
    return False


def _top_role(member):
    """Character the actor played most, which TMDB lists first."""
    roles = member.get('roles') or []
    return (roles[0].get('character') or '') if roles else ''


def _season_regulars(show):
    """Regulars across every season, deduped, in TMDB's billing order."""
    found = OrderedDict()
    for season in show.get('seasons', []):
        for member in season.get('credits', {}).get('cast', []):
            name = member.get('name', '')
            if not name:
                continue
            billing = member.get('order')
            billing = _MAX_CAST if billing is None else billing
            # billing is show-wide, so keep the season they ranked highest in
            if name not in found or billing < found[name][0]:
                found[name] = [billing, member]
    ranked = sorted(found.values(), key=lambda e: e[0])
    return [{
        'name': member.get('name', ''),
        'character': member.get('character', ''),
        'order': i,
        'profile_path': member.get('profile_path'),
    } for i, (_, member) in enumerate(ranked[:_MAX_CAST])]


class TmdbApi:
    """TMDB client for one scrape, holding the language preferences."""

    def __init__(self, settings):
        self._lang = settings['lang_details']
        img_lang = settings['lang_images'][:2]
        self._img_lang = '{},null'.format(img_lang) if img_lang == 'en' \
            else '{},en,null'.format(img_lang)
        self._is_english = self._lang.startswith('en')

    def search_shows(self, title, year=''):
        """Search results for a title, narrowed by first-air year if given."""
        params = {'query': title, 'language': self._lang}
        if year:
            params['first_air_date_year'] = year
        data = self._get('/search/tv', params)
        return data.get('results', []) if data else []

    def find_by_external_id(self, external_id, source):
        """IMDB/TVDB ID -> TMDB show ID via /find endpoint."""
        data = self._get('/find/{}'.format(external_id), {
            'external_source': '{}_id'.format(source),
        })
        if not data:
            return None
        results = data.get('tv_results', [])
        return str(results[0]['id']) if results else None

    def get_show_details(self, show_id):
        """Show metadata, per-season images and cast, batched and cached."""
        show_id = str(show_id)
        cached = _cache.get(show_id, {}).get('show')
        if cached:
            _touch(show_id)
            return cached

        # Evict oldest shows beyond limit
        while len(_cache) >= CACHE_LIMIT:
            evicted_id, _ = _cache.popitem(last=False)
            log.debug('cache evict show {}'.format(evicted_id))

        show = self._get('/tv/{}'.format(show_id), {
            'language': self._lang,
            'append_to_response': ','.join([
                'credits', 'content_ratings', 'external_ids',
                'images', 'videos', 'keywords',
            ]),
            'include_image_language': self._img_lang,
            'include_video_language': self._img_lang,
        })
        if not show:
            return None

        # A part that fails, after its request's retry, is left out and logged; a show without
        # one isn't cached, so that the next call asks again
        whole = True
        if not self._is_english and not show.get('overview'):
            try:
                en = self._get('/tv/{}'.format(show_id), {'language': 'en-US'})
            except RequestFailed as exc:
                en = None
                whole = _left_out('the English overview', exc)
            if en and en.get('overview'):
                show['overview'] = en['overview']

        if self._attach_season_data(show):
            whole = self._set_series_cast(show_id, show) and whole
        else:
            # Without every season's cast the regulars can't be told apart, and the whole run's
            # cast would be everyone who ever appeared: the show's own, its latest season's, stays
            whole = False
        if whole:
            _cache.setdefault(show_id, {})['show'] = show
            _touch(show_id)
        return show

    def _set_series_cast(self, show_id, show):
        """Show cast from the season regulars, or the whole run if none exist.

        Returns False when the whole run's cast was needed and its request failed.
        """
        cast = _season_regulars(show)
        if not cast:
            try:
                cast = self._aggregate_cast(show_id)
            except RequestFailed as exc:
                return _left_out("the show's cast", exc)
        if cast:
            show.setdefault('credits', {})['cast'] = cast
            log.debug('series cast: {}'.format(len(cast)))
        return True

    def _aggregate_cast(self, show_id):
        """Fallback for shows credited per episode with no season regulars."""
        data = self._get('/tv/{}/aggregate_credits'.format(show_id), {
            'language': self._lang,
        })
        if not data:
            return []
        return [{
            'name': member.get('name', ''),
            'character': _top_role(member),
            'order': i,
            'profile_path': member.get('profile_path'),
        } for i, member in enumerate(data.get('cast', [])[:_MAX_CAST])]

    def _attach_season_data(self, show):
        """Batch-fetch and attach per-season images and regular cast.

        Returns False when a batch's request failed, and its seasons' images and cast were left out.
        """
        whole = True
        seasons = show.get('seasons', [])
        season_map = {s.get('season_number', 0): s for s in seasons}
        show_id = show['id']

        season_keys = list(season_map.keys())
        per_call = _MAX_APPENDS // 2
        for i in range(0, len(season_keys), per_call):
            batch = season_keys[i:i + per_call]
            appends = []
            for n in batch:
                appends.append('season/{}/images'.format(n))
                appends.append('season/{}/credits'.format(n))
            try:
                data = self._get('/tv/{}'.format(show_id), {
                    'language': self._lang,
                    'append_to_response': ','.join(appends),
                    'include_image_language': self._img_lang,
                })
            except RequestFailed as exc:
                whole = _left_out('the images and cast of seasons {}'.format(batch), exc)
                continue
            if not data:
                # 404: the show is gone
                continue
            for snum in batch:
                images = data.get('season/{}/images'.format(snum))
                if images:
                    season_map[snum]['images'] = images
                credits = data.get('season/{}/credits'.format(snum))
                if credits:
                    season_map[snum]['credits'] = credits
        return whole

    def prefetch_episodes(self, show_id):
        """Pre-fetch the show's episodes.

        Only a whole guide is kept: a request that fails raises RequestFailed, nothing is kept,
        and the next call asks again.
        """
        show_id = str(show_id)
        entry = _cache.get(show_id, {})
        if 'episodes' in entry:
            _touch(show_id)
            return

        show = entry.get('show')
        if not show:
            show = self.get_show_details(show_id)
        if not show:
            return

        season_nums = [
            s.get('season_number', 0) for s in show.get('seasons', [])
            if not s.get('stub')
        ]

        all_seasons = self._fetch_all_seasons(show_id, season_nums)
        episodes = self._fetch_episode_extras(
            show_id, season_nums, all_seasons
        )

        if not self._is_english:
            self._episode_lang_fallback(show_id, episodes)

        _cache.setdefault(show_id, {})['episodes'] = episodes
        _touch(show_id)
        evict_episodes()

    def _fetch_all_seasons(self, show_id, season_nums):
        """Phase 1: Fetch full season data via show endpoint appends."""
        result = {}
        for i in range(0, len(season_nums), _MAX_APPENDS):
            batch = season_nums[i:i + _MAX_APPENDS]
            data = self._get('/tv/{}'.format(show_id), {
                'language': self._lang,
                'append_to_response': ','.join(
                    'season/{}'.format(n) for n in batch
                ),
            })
            if not data:
                # 404: the show is gone; a failure raises RequestFailed instead
                continue
            for snum in batch:
                # TMDB leaves out a season it hasn't, such as an episode group's stub
                sd = data.get('season/{}'.format(snum))
                if sd:
                    result[snum] = sd
        return result

    def _fetch_episode_extras(self, show_id, season_nums, all_seasons):
        """Phase 2: Fetch episode images and external_ids, marking a failed batch for retry."""
        episodes = {}
        pending = []
        for snum in season_nums:
            sd = all_seasons.get(snum)
            if not sd:
                continue
            for e in sd.get('episodes', []):
                if 'episode_number' in e:
                    pending.append((snum, e['episode_number'], e))

        per_call = _MAX_APPENDS // 2
        for i in range(0, len(pending), per_call):
            batch = pending[i:i + per_call]
            appends = []
            for snum, en, _ in batch:
                prefix = 'season/{}/episode/{}'.format(snum, en)
                appends.extend([prefix + '/images', prefix + '/external_ids'])

            params = {
                'language': self._lang,
                'append_to_response': ','.join(appends),
                'include_image_language': self._img_lang,
            }
            try:
                data = self._get('/tv/{}'.format(show_id), params)
            except RequestFailed:
                # the guide itself is whole: each of these episodes' details asks for its own
                # images and IDs, and fails if it can't get them
                data = None

            for snum, en, base in batch:
                ep = dict(base)
                if data is None:
                    ep['_retry'] = True
                else:
                    prefix = 'season/{}/episode/{}'.format(snum, en)
                    img = data.get(prefix + '/images')
                    ext = data.get(prefix + '/external_ids')
                    if img:
                        ep['images'] = img
                    if ext:
                        ep['external_ids'] = ext
                episodes[(snum, en)] = ep

        return episodes

    def _episode_lang_fallback(self, show_id, episodes):
        """Fill missing episode names/overviews from English."""
        need = set()
        for (snum, enum), ep in episodes.items():
            name = ep.get('name') or ''
            if (not name or not ep.get('overview')
                    or name == 'Episode {}'.format(enum)):
                need.add(snum)

        for snum in need:
            try:
                en = self._get(
                    '/tv/{}/season/{}'.format(show_id, snum),
                    {'language': 'en-US'}
                )
            except RequestFailed as exc:
                # The guide is kept without it: not keeping it would cost a request an episode
                _left_out('the English text of season {}'.format(snum), exc)
                continue
            if not en:
                # 404
                continue
            for en_ep in en.get('episodes', []):
                enum = en_ep.get('episode_number', 0)
                ep = episodes.get((snum, enum))
                if not ep:
                    continue
                name = ep.get('name') or ''
                if not name or name == 'Episode {}'.format(enum):
                    if en_ep.get('name'):
                        ep['name'] = en_ep['name']
                if not ep.get('overview') and en_ep.get('overview'):
                    ep['overview'] = en_ep['overview']

    def get_episode(self, show_id, season_num, episode_num):
        """Cache-first episode read, one API call on a miss or a failed prefetch batch.

        A miss, on an interpreter that didn't list the show, asks for the episode alone: in a
        scan's replay that cost fewer requests than fetching the show's guide or the season.
        """
        show_id = str(show_id)
        _touch(show_id)
        cached = _cache.get(show_id, {}).get('episodes', {}).get(
            (season_num, episode_num)
        )
        if cached and not cached.get('_retry'):
            return cached

        data = self._get(
            '/tv/{}/season/{}/episode/{}'.format(
                show_id, season_num, episode_num
            ), {
                'language': self._lang,
                'append_to_response': 'images,external_ids',
                'include_image_language': self._img_lang,
            }
        )
        if not data:
            # 404: no such episode, or no images and IDs for it
            return cached
        if cached:
            del cached['_retry']
            cached['images'] = data.get('images', {})
            cached['external_ids'] = data.get('external_ids', {})
            return cached
        # Not kept: 'episodes' holds only a whole guide, which getepisodelist would otherwise
        # take for the show's
        return data

    def get_cached_episodes(self, show_id):
        """All cached episodes for iteration. Empty dict if not prefetched."""
        return _cache.get(str(show_id), {}).get('episodes', {})

    def get_episode_group(self, group_id):
        """Fetch alternate episode ordering."""
        return self._get('/tv/episode_group/{}'.format(group_id), {})

    def _get(self, path, params):
        """GET a TMDB endpoint: parsed JSON, or None for a 404.

        Raises RequestFailed when the request fails, after one retry.
        """
        query = dict(params, api_key=TMDB_API_KEY)
        url = '{}{}?{}'.format(_BASE, path, urlencode(query))
        log.debug('TMDB GET {}'.format(path))
        return get_json(url, _HEADERS, 'TMDB GET {}'.format(path))
