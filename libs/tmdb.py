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

import json, six
from pprint import pformat
import requests
from requests.exceptions import HTTPError
from . import cache, data_utils, settings
from .utils import logger
try:
    from typing import Text, Optional, Union, List, Dict, Any  # pylint: disable=unused-import
    InfoType = Dict[Text, Any]  # pylint: disable=invalid-name
except ImportError:
    pass

# Same key as built-in XML scraper
BASE_URL = 'https://api.themoviedb.org/3/{}?api_key=f090bb54758cabf231fb605d3e3e0468&language=' + settings.LANG
EPISODE_GROUP_URL = BASE_URL.format('tv/episode_group/{}')
SEARCH_URL = BASE_URL.format('search/tv')
FIND_URL = BASE_URL.format('find/{}')
SHOW_URL = BASE_URL.format('tv/{}')
SEASON_URL = BASE_URL.format('tv/{}/season/{}')
EPISODE_URL = BASE_URL.format('tv/{}/season/{}/episode/{}')
FANARTTV_URL = 'https://webservice.fanart.tv/v3/tv/{}?api_key=384afe262ee0962545a752ff340e3ce4'
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
    # logger.debug('themoviedb response:\n{}'.format(pformat(json_response)))
    return json_response


def search_show(title, year=None):
    # type: (Text) -> List[InfoType]
    """
    Search for a single TV show

    :param title: TV show title to search
    : param year: the year to search (optional)
    :return: a list with found TV shows
    """
    results = []
    ext_media_id = data_utils.parse_media_id(title)
    if ext_media_id:
        if ext_media_id['type'] == 'tmdb_id':
            search_url = SHOW_URL.format(ext_media_id['title'])
            params = {}
        else:
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
            if ext_media_id['type'] == 'tmdb_id':
                if resp.get('success') == 'false':
                    results = []
                else:
                    results = [resp]
            else:
                results = resp.get('tv_results', [])
        else:
            results = resp.get('results', [])
    except HTTPError as exc:
        logger.error('themoviedb returned an error: {}'.format(exc))
    return results


def load_episode_list(show_info, season_map, ep_grouping):
    # type: (Text) -> List[InfoType]
    """Load episode list from themoviedb.org API"""
    episode_list = []
    if ep_grouping is not None:
        logger.debug('Getting episodes with episode grouping of ' + ep_grouping)
        episode_group_url = EPISODE_GROUP_URL.format(ep_grouping)
        try:
            custom_order = _load_info(episode_group_url)
        except HTTPError as exc:
            logger.error('themoviedb returned an error: {}'.format(exc))
            custom_order = None
        if custom_order is not None:
            show_info['seasons'] = []
            season_num = 1
            for custom_season in custom_order.get('groups', []):
                ep_num = 1
                season_episodes = []
                current_season = season_map.get(str(custom_season['episodes'][0]['season_number']), {}).copy()
                current_season['name'] = custom_season['name']
                current_season['season_number'] = season_num
                for episode in custom_season['episodes']:
                    episode['org_seasonnum'] = episode['season_number']
                    episode['org_epnum'] = episode['episode_number']
                    episode['season_number'] = season_num
                    episode['episode_number'] = ep_num
                    season_episodes.append(episode)
                    episode_list.append(episode)
                    ep_num = ep_num + 1
                current_season['episodes'] = season_episodes
                show_info['seasons'].append(current_season)
                season_num = season_num + 1
    else:
        show_info['seasons'] = []
        for key, value in six.iteritems(season_map):
            show_info['seasons'].append(value)
        for season in show_info.get('seasons', []):
            for episode in season.get('episodes', []):
                episode['org_seasonnum'] = episode['season_number']
                episode['org_epnum'] = episode['episode_number']
                episode_list.append(episode)
    show_info['episodes'] = episode_list
    return show_info


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
        season_map = {}
        for season in show_info.get('seasons', []):
            season_url = SEASON_URL.format(show_id, season['season_number'])
            params = {}
            params['append_to_response'] = 'credits,images'
            params['include_image_language'] = '%s,null' % settings.LANG[0:2]
            try:
                season_info = _load_info(season_url, params)
            except HTTPError as exc:
                logger.error('themoviedb returned an error: {}'.format(exc))
                season_info = {}
            season_map[str(season['season_number'])] = season_info
        show_info = load_episode_list(show_info, season_map, ep_grouping)
        show_info = load_fanarttv_art(show_info)
        cast_check = []
        cast = []
        for season in reversed(show_info.get('seasons', [])):
            for cast_member in season.get('credits', {}).get('cast', []):
                if cast_member['name'] not in cast_check:
                    cast.append(cast_member)
                    cast_check.append(cast_member['name'])
        show_info['credits']['cast'] = cast
        logger.debug('saving show info to the cache:\n{}'.format(pformat(show_info)))
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


def load_fanarttv_art(show_info):
    # type: (Text) -> Optional[InfoType]
    """
    Add fanart.tv images for a show

    :param show_info: the current show info
    :return: show info
    """
    tvdb_id = show_info.get('external_ids', {}).get('tvdb_id')
    artwork_enabled = False
    for artcheck in settings.FANARTTV_ART:
        artwork_enabled = artwork_enabled or artcheck
        if artwork_enabled:
            break
    if tvdb_id and artwork_enabled:
        fanarttv_url = FANARTTV_URL.format(tvdb_id)
        try:
            artwork = _load_info(fanarttv_url)
        except HTTPError as exc:
            logger.error('fanart.tv returned an error: {}'.format(exc))
            return show_info
        for fanarttv_type, tmdb_type in six.iteritems(settings.FANARTTV_MAPPING):
            if settings.FANARTTV_ART[tmdb_type]:
                if not show_info['images'].get(tmdb_type) and not tmdb_type.startswith('season'):
                    show_info['images'][tmdb_type] = []
                for item in artwork.get(fanarttv_type, []):
                    lang = item.get('lang')
                    filepath = ''
                    if lang == '' or lang == '00' or lang == settings.LANG[0:2]:
                        filepath = item.get('url')
                    if filepath:
                        if tmdb_type.startswith('season'):
                            image_type = tmdb_type[6:]
                            for s in range(len(show_info.get('seasons', []))):
                                season_num = show_info['seasons'][s]['season_number']
                                artseason = item.get('season', '')
                                if not show_info['seasons'][s].get('images'):
                                    show_info['seasons'][s]['images'] = {}
                                if not show_info['seasons'][s]['images'].get(image_type):
                                    show_info['seasons'][s]['images'][image_type] = []                                
                                if artseason == '' or artseason == str(season_num):
                                    show_info['seasons'][s]['images'][image_type].append({'file_path':filepath, 'type':'fanarttv'})
                        else:
                            show_info['images'][tmdb_type].append({'file_path':filepath, 'type':'fanarttv'})
    return show_info
    