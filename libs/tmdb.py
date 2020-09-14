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

import xbmcaddon
from pprint import pformat
import requests
from requests.exceptions import HTTPError
from . import cache
from .utils import logger, safe_get
try:
    from typing import Text, Optional, Union, List, Dict, Any  # pylint: disable=unused-import
    InfoType = Dict[Text, Any]  # pylint: disable=invalid-name
except ImportError:
    pass
import tmdbsimple as tmdb

# Same key as built-in XML scraper
tmdb.API_KEY = 'f090bb54758cabf231fb605d3e3e0468'
ADDON_SETTINGS = xbmcaddon.Addon()
LANG = ADDON_SETTINGS.getSettingString('language')
CERT_COUNTRY = ADDON_SETTINGS.getSettingString('tmdbcertcountry')
CERT_PREFIX = ADDON_SETTINGS.getSettingString('certprefix')

EPISODE_GROUP_URL = 'https://api.themoviedb.org/3/tv/episode_group/{}?api_key=%s' % tmdb.API_KEY
HEADERS = (
    ('User-Agent', 'Kodi scraper for tvmaze.com by pkscout; pkscout@kodi.tv'),
    ('Accept', 'application/json'),
)
SESSION = requests.Session()
SESSION.headers.update(dict(HEADERS))


def search_show(title, year=None):
    # type: (Text) -> List[InfoType]
    """
    Search a single TV show

    :param title: TV show title to search
    :return: a list with found TV shows
    """
    srch = tmdb.Search()
    if not year:
        resp = srch.tv(query=title)
    else:
        resp = srch.tv(query=title, first_air_date_year=year)
    return srch.results


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


def load_episode_list(show_info):
    # type: (Text) -> List[InfoType]
    """Load episode list from themoviedb.org API"""
    episode_list = []
    if show_info['ep_grouping'] is not None:
        logger.debug('OK, this is it. getting episodes with episode grouping of ' + show_info['ep_grouping'])
        # tmdbsimple doesn't have an abstraction for episode groups, so we have to do this by hand
        episode_group_url = EPISODE_GROUP_URL.format(show_info['ep_grouping'])
        try:
            custom_order = _load_info(episode_group_url)
        except HTTPError as exc:
            logger.error('themoviedb returned an error: {}'.format(exc))
            custom_order = None
        if custom_order is not None:
            try:
                custom_list = custom_order['groups']
            except (IndexError, KeyError):
                custom_list = []
            season_num = 1
            for season in custom_list:
                ep_num = 1
                for episode in season['episodes']:
                    episode['season_number'] = season_num
                    episode['episode_number'] = ep_num
                    episode_list.append(episode)
                    ep_num = ep_num + 1
                season_num = season_num + 1
            if episode_list:
                return episode_list
    logger.debug('loading standard episode order')
    for season in show_info['seasons']:
        q_season = tmdb.TV_Seasons(show_info['id'], season['season_number'])
        resp = q_season.info(language=LANG)
        episode_list = episode_list + resp['episodes']
    return episode_list


def load_show_info(show_id, ep_grouping=None):
    # type: (Text) -> Optional[InfoType]
    """
    Get full info for a single show

    :param show_id: themoviedb.org show ID
    :return: show info or None
    """
    if ep_grouping is not None:
        logger.debug('last step before loading show, still have an episode group of ' + ep_grouping)
    else:
        logger.debug('last step before loading show, no episide group')
    show_info = cache.load_show_info_from_cache(show_id)
    if show_info is None:
        logger.debug('no cache file found, loading from scratch')
        show = tmdb.TV(show_id)
        if show is not None:
            show_info = show.info(language=LANG)
            show_info.update(show.credits(language=LANG))
            show_info.update(show.images())
            show_info.update(show.content_ratings(language=LANG))
            show_info.update(show.external_ids())
            show_info['ep_grouping'] = ep_grouping
            show_info['episodes'] = load_episode_list(show_info)
            cache.cache_show_info(show_info)
        else:
            show_info = None
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
            episode_info = {}
        return episode_info
    return None
