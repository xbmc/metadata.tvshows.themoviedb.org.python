# coding: utf-8
#
# Copyright (C) 2019, Roman Miroshnychenko aka Roman V.M. <roman1972@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Functions to interact with TVmaze API"""

from __future__ import absolute_import, unicode_literals

import json
from pprint import pformat
import requests
from requests.exceptions import HTTPError
from . import cache, settings
from .utils import logger, safe_get
try:
    from typing import Text, Optional, Union, List, Dict, Any  # pylint: disable=unused-import
    InfoType = Dict[Text, Any]  # pylint: disable=invalid-name
except ImportError:
    pass

# Same key as built-in XML scraper
BASE_URL = 'https://api.themoviedb.org/3/'
API_BASE = '?api_key=f090bb54758cabf231fb605d3e3e0468'
LANG_BASE = '&language=' + settings.LANG
EPISODE_GROUP_URL = BASE_URL + 'tv/episode_group/{}' + API_BASE
SEARCH_URL = BASE_URL + 'search/tv' + API_BASE + LANG_BASE
FIND_URL = BASE_URL + 'find/{}' + API_BASE + LANG_BASE
SHOW_URL = BASE_URL +'tv/{}' + API_BASE + LANG_BASE
SEASON_URL = BASE_URL +'tv/{}/season/{}' + API_BASE + LANG_BASE
EPISODE_URL = BASE_URL + 'tv/{}/season/{}/episode/{}' + API_BASE + LANG_BASE
HEADERS = (
    ('User-Agent', 'Kodi scraper for themoviedb.org by pkscout; pkscout@kodi.tv'),
    ('Accept', 'application/json'),
)
SESSION = requests.Session()
SESSION.headers.update(dict(HEADERS))


def _load_info(url, params=None):
    # type: (Text, Optional[Dict[Text, Union[Text, List[Text]]]]) -> Union[dict, list]
    """
    Load info from themoviedb

    :param url: API endpoint URL
    :param params: URL query params
    :return: API response
    :raises requests.exceptions.HTTPError: if any error happens
    """
    logger.debug('Calling URL "{}" with params {}'.format(url, params))
    response = SESSION.get(url, params=params)
    if not response.ok:
        response.raise_for_status()
    json_response = response.json()
    logger.debug('themoviedb response:\n{}'.format(pformat(json_response)))
    return json_response


def _parse_media_id(title):
    title = title.lower()
    if title.startswith('tt') and title[2:].isdigit():
        return {'type': 'imdb_id', 'title': title} # IMDB ID works alone because it is clear
    elif title.startswith('imdb/tt') and title[7:].isdigit(): # IMDB ID with prefix to match
        return {'type': 'imdb_id', 'title': title[5:]} # IMDB ID works alone because it is clear
    elif title.startswith('tvdb/') and title[5:].isdigit(): # TVDB ID
        return {'type': 'tvdb_id', 'title': title[5:]}
    return None


def search_show(title, year=None):
    # type: (Text) -> List[InfoType]
    """
    Search for a single TV show

    :param title: TV show title to search
    : param year: the year to search (optional)
    :return: a list with found TV shows
    """
    results = []
    ext_media_id = _parse_media_id(title)
    if ext_media_id:
        search_url = FIND_URL.format(ext_media_id['title'])
        params = {'external_source':ext_media_id['type']}
    else:
        search_url = SEARCH_URL
        params = {'query': title}
        if year:
            params.update({'first_air_date_year': str(year)})
    try:
        resp = _load_info(search_url, params)
        if ext_media_id:
            results = resp.get('tv_results', [])
        else:
            results = resp.get('results', [])
    except HTTPError as exc:
        logger.error('themoviedb returned an error: {}'.format(exc))
    return results


def load_episode_list(show_info):
    # type: (Text) -> List[InfoType]
    """Load episode list from themoviedb.org API"""
    if show_info.get('episodes'):
        return show_info['episodes']
    episode_list = []
    custom_list = {}
    if show_info['ep_grouping'] is not None:
        logger.debug('Getting episodes with episode grouping of ' + show_info['ep_grouping'])
        episode_group_url = EPISODE_GROUP_URL.format(show_info['ep_grouping'])
        try:
            custom_order = _load_info(episode_group_url)
        except HTTPError as exc:
            logger.error('themoviedb returned an error: {}'.format(exc))
            custom_order = None
        if custom_order is not None:
            season_num = 1
            for season in custom_order.get('groups', []):
                ep_num = 1
                for episode in season['episodes']:
                    episode['org_seasonnum'] = episode['season_number']
                    episode['org_epnum'] = episode['episode_number']
                    episode['season_number'] = season_num
                    episode['episode_number'] = ep_num
                    episode_list.append(episode)
                    ep_num = ep_num + 1
                season_num = season_num + 1
    else:
        for season in show_info.get('seasons', []):
            for episode in season.get('episodes', []):
                episode['org_seasonnum'] = episode['season_number']
                episode['org_epnum'] = episode['episode_number']
                episode_list.append(episode)
    show_info['episodes'] = episode_list
    cache.cache_show_info(show_info)
    return episode_list


def load_show_info(show_id, ep_grouping=None):
    # type: (Text) -> Optional[InfoType]
    """
    Get full info for a single show

    :param show_id: themoviedb.org show ID
    :return: show info or None
    """
    show_info = cache.load_show_info_from_cache(show_id)
    if show_info is None:
        logger.debug('no cache file found, loading from scratch')
        show_url = SHOW_URL.format(show_id)
        params = {}
        params['append_to_response'] = 'credits,content_ratings,external_ids,images'
        params['include_image_language'] = '%s,null' % settings.LANG[0:2]
        try:
            show_info = _load_info(show_url, params)
        except HTTPError as exc:
            logger.error('themoviedb returned an error: {}'.format(exc))
            return None
        show_info['ep_grouping'] = ep_grouping
        i = 0
        for season in show_info.get('seasons', []):
            season_url = SEASON_URL.format(show_id, season['season_number'])
            params = {}
            params['append_to_response'] = 'credits,images'
            params['include_image_language'] = '%s,null' % settings.LANG[0:2]
            try:
                season_info = _load_info(season_url, params)
            except HTTPError as exc:
                logger.error('themoviedb returned an error: {}'.format(exc))
                season_info = None
            if season_info:
                show_info['seasons'][i] = season_info
            i = i + 1
        cast_check = []
        cast = []
        for season in reversed(show_info.get('seasons', [])):
            for cast_member in season.get('credits', {}).get('cast', []):
                if cast_member['name'] not in cast_check:
                    cast.append(cast_member)
                    cast_check.append(cast_member['name'])
        show_info['credits']['cast'] = cast
        logger.debug('saving show info to the cache')
        cache.cache_show_info(show_info)
    return show_info


def load_episode_info(show_id, episode_id):
    # type: (Text, Text) -> Optional[InfoType]
    """
    Load episode info

    :param show_id:
    :param episode_id:
    :return: episode info or None
    """
    show_info = load_show_info(show_id)
    if show_info is not None:
        try:
            episode_info = show_info['episodes'][int(episode_id)]
        except KeyError:
            return None
        # this ensures we are using the season/ep from the episode grouping if provided
        ep_url = EPISODE_URL.format(show_info['id'], episode_info['org_seasonnum'], episode_info['org_epnum'])
        params = {}
        params['append_to_response'] = 'credits,external_ids,images'
        params['include_image_language'] = '%s,null' % settings.LANG[0:2]
        try:
            ep_return = _load_info(ep_url, params)
        except HTTPError as exc:
            logger.error('themoviedb returned an error: {}'.format(exc))
            return None
        ep_return['season_number'] = episode_info['season_number']
        ep_return['episode_number'] = episode_info['episode_number']
        ep_return['org_seasonnum'] = episode_info['org_seasonnum']
        ep_return['org_epnum'] = episode_info['org_epnum']
        show_info['episodes'][int(episode_id)] = ep_return
        cache.cache_show_info(show_info)
        return ep_return
    return None
