# coding: utf-8
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

"""Functions to interact with various web site APIs"""

from __future__ import absolute_import, unicode_literals

import json
from pprint import pformat
import requests
from requests.exceptions import HTTPError
from . import settings
from .utils import logger
try:
    from typing import Text, Optional, Union, List, Dict, Any  # pylint: disable=unused-import
    InfoType = Dict[Text, Any]  # pylint: disable=invalid-name
except ImportError:
    pass

HEADERS = (
    ('User-Agent', 'Kodi TV Show scraper by Team Kodi/; contact pkscout@kodi.tv'),
    ('Accept', 'application/json'),
)
SESSION = requests.Session()
SESSION.headers.update(dict(HEADERS))


def set_headers(headers):
    SESSION.headers.update(headers)


def load_info(url, params=None, default=None):
    # type: (Text, Optional[Dict[Text, Union[Text, List[Text]]]]) -> Union[dict, list]
    """
    Load info from external api

    :param url: API endpoint URL
    :param params: URL query params
    :return: API response or default on error
    """
    logger.debug('Calling URL "{}" with params {}'.format(url, params))
    try:
        response = SESSION.get(url, params=params)
    except HTTPError as exc:
        logger.error('themoviedb returned an error: {}'.format(exc))
        response = None
    if response is None:
        return default
    json_response = response.json()
    if settings.VERBOSELOG:
        logger.debug('the api response:\n{}'.format(pformat(json_response)))
    return json_response
