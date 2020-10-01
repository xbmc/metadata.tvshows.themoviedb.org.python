# -*- coding: UTF-8 -*-
#
# Copyright (C) 2020, Team Kodi
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
# pylint: disable=missing-docstring

"""Functions to interact with Trakt API"""

from __future__ import absolute_import, unicode_literals

from . import api_utils, settings
from .utils import logger
try:
    from typing import Text, Optional, Union, List, Dict, Any  # pylint: disable=unused-import
    InfoType = Dict[Text, Any]  # pylint: disable=invalid-name
except ImportError:
    pass

BASE_URL = 'https://api.trakt.tv/shows/{}'
SHOW_URL = BASE_URL + '?extended=full'
EP_URL = BASE_URL + '/seasons/{}/episodes/{}/ratings'
HEADERS = (
    ('trakt-api-key', settings.TRAKT_CLOWNCAR),
    ('trakt-api-version', '2'),
    ('Content-Type', 'application/json'),
)
api_utils.set_headers(dict(HEADERS))


def get_details(imdb_id, season=None, episode=None):
    result = {}
    if season and episode:
        url = EP_URL.format(imdb_id, season, episode)
    else:
        url = SHOW_URL.format(imdb_id)
    resp = api_utils.load_info(url, default={})
    rating =resp.get('rating')
    votes = resp.get('votes')
    if votes and rating:
        result['ratings'] = {'trakt': {'votes': votes, 'rating': rating}}
    return result
