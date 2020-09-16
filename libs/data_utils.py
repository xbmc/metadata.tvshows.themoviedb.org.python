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
#
# This is based on the metadata.tvmaze scrapper by Roman Miroshnychenko aka Roman V.M.

"""Functions to process data"""

from __future__ import absolute_import, unicode_literals

import re
from collections import OrderedDict, namedtuple
import six
from .utils import safe_get, logger
from . import settings

try:
    from typing import Optional, Text, Dict, List, Any  # pylint: disable=unused-import
    from xbmcgui import ListItem  # pylint: disable=unused-import
    InfoType = Dict[Text, Any]  # pylint: disable=invalid-name
except ImportError:
    pass

TAG_RE = re.compile(r'<[^>]+>')
SHOW_ID_REGEXPS = (
    r'(tvmaze)\.com/shows/(\d+)/[\w\-]',
    r'(thetvdb)\.com/.*?series/(\d+)',
    r'(thetvdb)\.com[\w=&\?/]+id=(\d+)',
    r'(imdb)\.com/[\w/\-]+/(tt\d+)',
    r'(themoviedb)\.org/tv/(\d+).*/episode_group/(.*)',
    r'(themoviedb)\.org/tv/(\d+)'
)
SUPPORTED_ARTWORK_TYPES = {'poster', 'banner'}
IMAGE_SIZES = ('large', 'original', 'medium')
CLEAN_PLOT_REPLACEMENTS = (
    ('<b>', '[B]'),
    ('</b>', '[/B]'),
    ('<i>', '[I]'),
    ('</i>', '[/I]'),
    ('</p><p>', '[CR]'),
)

UrlParseResult = namedtuple('UrlParseResult', ['provider', 'show_id', 'ep_grouping'])



def _clean_plot(plot):
    # type: (Text) -> Text
    """Replace HTML tags with Kodi skin tags"""
    for repl in CLEAN_PLOT_REPLACEMENTS:
        plot = plot.replace(repl[0], repl[1])
    plot = TAG_RE.sub('', plot)
    return plot


def _set_cast(show_info, list_item):
    # type: (InfoType, ListItem) -> ListItem
    """Extract cast from show info dict"""
    cast = []
    for item in show_info['credits']['cast']:
        data = {
            'name': item['name'],
            'role': item['character'],
            'order': item['order'],
        }
        thumb = None
        if safe_get(item, 'profile_path') is not None:
            thumb = settings.IMAGEROOTURL + item['profile_path']
        if thumb:
            data['thumbnail'] = thumb
        cast.append(data)
    list_item.setCast(cast)
    return list_item


def _get_credits(show_info):
    # type: (InfoType) -> List[Text]
    """Extract show creator(s) from show info"""
    credits_ = []
    for item in show_info['created_by']:
        credits_.append(item['name'])
    return credits_


def _set_unique_ids(show_info, list_item):
    # type: (InfoType, ListItem) -> ListItem
    """Extract unique ID in various online databases"""
    unique_ids = {'themoviedb': str(show_info['id'])}
    for key, value in six.iteritems(safe_get(show_info, 'externals_ids', {})):
        if not key == 'freebase_mid':
            key = key[:-3]
            unique_ids[key] = str(value)
    list_item.setUniqueIDs(unique_ids, 'themoviedb')
    return list_item


def _set_rating(show_info, list_item):
    # type: (InfoType, ListItem) -> ListItem
    """Set show rating"""
    if safe_get(show_info, 'vote_average') is not None:
        rating = float(show_info['vote_average'])
        list_item.setRating('themoviedb', rating, defaultt=True)
    return list_item


def _extract_artwork_url(resolutions):
    # type: (Dict[Text, Text]) -> Text
    """Extract image URL from the list of available resolutions"""
    url = ''
    for image_size in IMAGE_SIZES:
        url = safe_get(resolutions, image_size, '')
        if not isinstance(url, six.text_type):
            url = safe_get(url, 'url', '')
            if url:
                break
    return url


def _add_season_info(show_info, list_item):
    # type: (InfoType, ListItem) -> ListItem
    """Add info for show seasons"""
    for season in show_info['seasons']:
        list_item.addSeason(season['season_number'], safe_get(season, 'name', ''))
        image = safe_get(season, 'poster_path')
        if image is not None:
            url = settings.IMAGEROOTURL + season['poster_path']
            list_item.addAvailableArtwork(url, 'poster', season=season['season_number'])
    return list_item


def set_show_artwork(show_info, list_item):
    # type: (InfoType, ListItem) -> ListItem
    """Set available images for a show"""
    fanart_list = []
    for backdrop in safe_get(show_info, 'backdrops', {}):
        url = settings.IMAGEROOTURL + backdrop['file_path']
        fanart_list.append({'image': url})
    if fanart_list:
        list_item.setAvailableFanart(fanart_list)
    for poster in safe_get(show_info, 'posters', {}):
        url = settings.IMAGEROOTURL + poster['file_path']
        list_item.addAvailableArtwork(url, 'poster')
    return list_item


def add_main_show_info(list_item, show_info, full_info=True):
    # type: (ListItem, InfoType, bool) -> ListItem
    """Add main show info to a list item"""
    plot = _clean_plot(safe_get(show_info, 'overview', ''))
    genre_list = safe_get(show_info, 'genres', {})
    genres = []
    for genre in genre_list:
        genres.append(genre['name'])
    video = {
        'plot': plot,
        'plotoutline': plot,
        'genre': genres,
        'title': show_info['name'],
        'tvshowtitle': show_info['name'],
        'status': safe_get(show_info, 'status', ''),
        'mediatype': 'tvshow',
        # This property is passed as "url" parameter to getepisodelist call
        'episodeguide': str(show_info['id']),
    }
    if show_info['networks']:
        network = show_info['networks'][0]
        country = network['origin_country']
        video['studio'] = '{0} ({1})'.format(network['name'], country)
        video['country'] = country
    if show_info['first_air_date']:
        video['year'] = int(show_info['first_air_date'][:4])
        video['premiered'] = show_info['first_air_date']
    content_ratings = show_info.get('content_ratings', {}).get('results', {})
    if content_ratings:
        mpaa = ''
        mpaa_backup = ''
        for content_rating in content_ratings:
            iso = content_rating.get('iso_3166_1', '').lower()
            if iso == 'us':
                mpaa_backup = content_rating.get('rating')
            if iso == settings.CERT_COUNTRY.lower():
                mpaa = content_rating.get('rating', '')
        if not mpaa:
            mpaa = mpaa_backup
        if mpaa:
            video['Mpaa'] = settings.CERT_PREFIX + mpaa
    if full_info:
        video['credits'] = _get_credits(show_info)
        list_item = set_show_artwork(show_info, list_item)
        list_item = _add_season_info(show_info, list_item)
        list_item = _set_cast(show_info, list_item)
    else:
        image = safe_get(show_info, 'poster_path', '')
        if image:
            image_url = settings.IMAGEROOTURL + image
            list_item.addAvailableArtwork(image_url, 'poster')
    list_item.setInfo('video', video)
    list_item = _set_rating(show_info, list_item)
    # This is needed for getting artwork
    list_item = _set_unique_ids(show_info, list_item)
    return list_item


def add_episode_info(list_item, episode_info, full_info=True):
    # type: (ListItem, InfoType, bool) -> ListItem
    """Add episode info to a list item"""
    video = {
        'title': episode_info['name'],
        'season': episode_info['season_number'],
        'episode': episode_info['episode_number'],
        'mediatype': 'episode',
    }
    if safe_get(episode_info, 'air_date') is not None:
        video['aired'] = episode_info['air_date']
    if full_info:
        summary = safe_get(episode_info, 'overview')
        if summary is not None:
            video['plot'] = video['plotoutline'] = _clean_plot(summary)
        if safe_get(episode_info, 'air_date') is not None:
            video['premiered'] = episode_info['air_date']
    list_item.setInfo('video', video)
    for image in episode_info.get('images', {}).get('stills', []):
        img_path = image.get('file_path')
        if img_path:
            image_url = settings.IMAGEROOTURL + img_path
            list_item.addAvailableArtwork(image_url, 'thumb')
    list_item.setUniqueIDs({'themoviedb': str(episode_info['id'])}, 'themoviedb')
    return list_item


def parse_nfo_url(nfo):
    # type: (Text) -> Optional[UrlParseResult]
    """Extract show ID from NFO file contents"""
    for regexp in SHOW_ID_REGEXPS:
        logger.debug('****** trying regex to match service from parsing nfo:')
        logger.debug(regexp)
        show_id_match = re.search(regexp, nfo, re.I)
        if show_id_match:
            logger.debug('match group 1: ' + show_id_match.group(1))
            logger.debug('match group 2: ' + show_id_match.group(2))
            try:
                ep_grouping = show_id_match.group(3)
            except IndexError:
                ep_grouping = None
            if ep_grouping is not None:
                logger.debug('match group 3: ' + ep_grouping)
            else:
                logger.debug('match group 3: None')
            return UrlParseResult(show_id_match.group(1), show_id_match.group(2), ep_grouping)
    return None
