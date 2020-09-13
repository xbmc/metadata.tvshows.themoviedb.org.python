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


def load_episode_list(show_info):
    # type: (Text) -> List[InfoType]
    """Load episode list from themoviedb.org API"""
    episode_list = []
    for season in show_info['seasons']:
        q_season = tmdb.TV_Seasons(show_info['id'], season['season_number'])
        resp = q_season.info()
        episode_list = episode_list + resp['episodes']
    return episode_list


def load_show_info(show_id):
    # type: (Text) -> Optional[InfoType]
    """
    Get full info for a single show

    :param show_id: themoviedb.org show ID
    :return: show info or None
    """
    show_info = cache.load_show_info_from_cache(show_id)
    if show_info is None:
        show = tmdb.TV(show_id)
        if show is not None:
            show_info = show.info()
            show_info.update(show.credits())
            show_info.update(show.images())
            show_info.update(show.content_ratings())
            show_info.update(show.external_ids())
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
