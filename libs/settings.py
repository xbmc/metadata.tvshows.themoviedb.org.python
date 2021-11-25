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

import json
import sys
import urllib.parse
from .utils import logger
from . import api_utils
from xbmcaddon import Addon
from datetime import datetime, timedelta


def _get_date_numeric(datetime_):
    return (datetime_ - datetime(1970, 1, 1)).total_seconds()


def _get_configuration():
    logger.debug('getting configuration details')
    return api_utils.load_info('https://api.themoviedb.org/3/configuration', params={'api_key': TMDB_CLOWNCAR}, verboselog=VERBOSELOG)


def _load_base_urls():
    image_root_url = ADDON.getSettingString('originalUrl')
    preview_root_url = ADDON.getSettingString('previewUrl')
    last_updated = ADDON.getSettingString('lastUpdated')
    if not image_root_url or not preview_root_url or not last_updated or \
            float(last_updated) < _get_date_numeric(datetime.now() - timedelta(days=30)):
        conf = _get_configuration()
        if conf:
            image_root_url = conf['images']['secure_base_url'] + 'original'
            preview_root_url = conf['images']['secure_base_url'] + 'w780'
            ADDON.setSetting('originalUrl', image_root_url)
            ADDON.setSetting('previewUrl', preview_root_url)
            ADDON.setSetting('lastUpdated', str(
                _get_date_numeric(datetime.now())))
    return image_root_url, preview_root_url


ADDON = Addon()
TMDB_CLOWNCAR = 'af3a53eb387d57fc935e9128468b1899'
FANARTTV_CLOWNCAR = 'b018086af0e1478479adfc55634db97d'
TRAKT_CLOWNCAR = '90901c6be3b2de5a4fa0edf9ab5c75e9a5a0fef2b4ee7373d8b63dcf61f95697'
MAXIMAGES = 250
FANARTTV_MAPPING = {'showbackground': 'backdrops',
                    'tvposter': 'posters',
                    'tvbanner': 'banner',
                    'hdtvlogo': 'clearlogo',
                    'clearlogo': 'clearlogo',
                    'hdclearart': 'clearart',
                    'clearart': 'clearart',
                    'tvthumb': 'landscape',
                    'characterart': 'characterart',
                    'seasonposter': 'seasonposters',
                    'seasonbanner': 'seasonbanner',
                    'seasonthumb': 'seasonlandscape'
                    }

try:
    source_params = dict(urllib.parse.parse_qsl(sys.argv[2]))
except IndexError:
    source_params = {}
source_settings = json.loads(source_params.get('pathSettings', '{}'))

KEEPTITLE = source_settings.get(
    'keeporiginaltitle', ADDON.getSettingBool('keeporiginaltitle'))
CATLANDSCAPE = source_settings.get('cat_landscape', True)
STUDIOCOUNTRY = source_settings.get('studio_country', False)
ENABTRAILER = source_settings.get(
    'enab_trailer', ADDON.getSettingBool('enab_trailer'))
PLAYERSOPT = source_settings.get(
    'players_opt', ADDON.getSettingString('players_opt')).lower()
VERBOSELOG = source_settings.get(
    'verboselog', ADDON.getSettingBool('verboselog'))
LANG = source_settings.get('language', ADDON.getSettingString('language'))
CERT_COUNTRY = source_settings.get(
    'tmdbcertcountry', ADDON.getSettingString('tmdbcertcountry')).lower()
IMAGEROOTURL, PREVIEWROOTURL = _load_base_urls()

primary_rating = source_settings.get(
    'ratings', ADDON.getSettingString('ratings')).lower()
RATING_TYPES = [primary_rating]
if source_settings.get('imdbanyway', ADDON.getSettingBool('imdbanyway')) and primary_rating != 'imdb':
    RATING_TYPES.append('imdb')
if source_settings.get('traktanyway', ADDON.getSettingBool('traktanyway')) and primary_rating != 'trakt':
    RATING_TYPES.append('trakt')
if source_settings.get('tmdbanyway', ADDON.getSettingBool('tmdbanyway')) and primary_rating != 'tmdb':
    RATING_TYPES.append('tmdb')
FANARTTV_ENABLE = source_settings.get(
    'enable_fanarttv', ADDON.getSettingBool('enable_fanarttv'))
FANARTTV_CLIENTKEY = source_settings.get(
    'fanarttv_clientkey', ADDON.getSettingString('fanarttv_clientkey'))
ISOALPHAMAP = {
    'AF': 'AFG',
    'AX': 'ALA',
    'AL': 'ALB',
    'DZ': 'DZA',
    'AS': 'ASM',
    'AD': 'AND',
    'AO': 'AGO',
    'AI': 'AIA',
    'AQ': 'ATA',
    'AG': 'ATG',
    'AR': 'ARG',
    'AM': 'ARM',
    'AW': 'ABW',
    'AU': 'AUS',
    'AT': 'AUT',
    'AZ': 'AZE',
    'BS': 'BHS',
    'BH': 'BHR',
    'BD': 'BGD',
    'BB': 'BRB',
    'BY': 'BLR',
    'BE': 'BEL',
    'BZ': 'BLZ',
    'BJ': 'BEN',
    'BM': 'BMU',
    'BT': 'BTN',
    'BO': 'BOL',
    'BQ': 'BES',
    'BA': 'BIH',
    'BW': 'BWA',
    'BV': 'BVT',
    'BR': 'BRA',
    'IO': 'IOT',
    'BN': 'BRN',
    'BG': 'BGR',
    'BF': 'BFA',
    'BI': 'BDI',
    'CV': 'CPV',
    'KH': 'KHM',
    'CM': 'CMR',
    'CA': 'CAN',
    'KY': 'CYM',
    'CF': 'CAF',
    'TD': 'TCD',
    'CL': 'CHL',
    'CN': 'CHN',
    'CX': 'CXR',
    'CC': 'CCK',
    'CO': 'COL',
    'KM': 'COM',
    'CG': 'COG',
    'CD': 'COD',
    'CK': 'COK',
    'CR': 'CRI',
    'CI': 'CIV',
    'HR': 'HRV',
    'CU': 'CUB',
    'CW': 'CUW',
    'CY': 'CYP',
    'CZ': 'CZE',
    'DK': 'DNK',
    'DJ': 'DJI',
    'DM': 'DMA',
    'DO': 'DOM',
    'EC': 'ECU',
    'EG': 'EGY',
    'SV': 'SLV',
    'GQ': 'GNQ',
    'ER': 'ERI',
    'EE': 'EST',
    'SZ': 'SWZ',
    'ET': 'ETH',
    'FK': 'FLK',
    'FO': 'FRO',
    'FJ': 'FJI',
    'FI': 'FIN',
    'FR': 'FRA',
    'GF': 'GUF',
    'PF': 'PYF',
    'TF': 'ATF',
    'GA': 'GAB',
    'GM': 'GMB',
    'GE': 'GEO',
    'DE': 'DEU',
    'GH': 'GHA',
    'GI': 'GIB',
    'GR': 'GRC',
    'GL': 'GRL',
    'GD': 'GRD',
    'GP': 'GLP',
    'GU': 'GUM',
    'GT': 'GTM',
    'GG': 'GGY',
    'GN': 'GIN',
    'GW': 'GNB',
    'GY': 'GUY',
    'HT': 'HTI',
    'HM': 'HMD',
    'VA': 'VAT',
    'HN': 'HND',
    'HK': 'HKG',
    'HU': 'HUN',
    'IS': 'ISL',
    'IN': 'IND',
    'ID': 'IDN',
    'IR': 'IRN',
    'IQ': 'IRQ',
    'IE': 'IRL',
    'IM': 'IMN',
    'IL': 'ISR',
    'IT': 'ITA',
    'JM': 'JAM',
    'JP': 'JPN',
    'JE': 'JEY',
    'JO': 'JOR',
    'KZ': 'KAZ',
    'KE': 'KEN',
    'KI': 'KIR',
    'KP': 'PRK',
    'KR': 'KOR',
    'KW': 'KWT',
    'KG': 'KGZ',
    'LA': 'LAO',
    'LV': 'LVA',
    'LB': 'LBN',
    'LS': 'LSO',
    'LR': 'LBR',
    'LY': 'LBY',
    'LI': 'LIE',
    'LT': 'LTU',
    'LU': 'LUX',
    'MO': 'MAC',
    'MG': 'MDG',
    'MW': 'MWI',
    'MY': 'MYS',
    'MV': 'MDV',
    'ML': 'MLI',
    'MT': 'MLT',
    'MH': 'MHL',
    'MQ': 'MTQ',
    'MR': 'MRT',
    'MU': 'MUS',
    'YT': 'MYT',
    'MX': 'MEX',
    'FM': 'FSM',
    'MD': 'MDA',
    'MC': 'MCO',
    'MN': 'MNG',
    'ME': 'MNE',
    'MS': 'MSR',
    'MA': 'MAR',
    'MZ': 'MOZ',
    'MM': 'MMR',
    'NA': 'NAM',
    'NR': 'NRU',
    'NP': 'NPL',
    'NL': 'NLD',
    'NC': 'NCL',
    'NZ': 'NZL',
    'NI': 'NIC',
    'NE': 'NER',
    'NG': 'NGA',
    'NU': 'NIU',
    'NF': 'NFK',
    'MK': 'MKD',
    'MP': 'MNP',
    'NO': 'NOR',
    'OM': 'OMN',
    'PK': 'PAK',
    'PW': 'PLW',
    'PS': 'PSE',
    'PA': 'PAN',
    'PG': 'PNG',
    'PY': 'PRY',
    'PE': 'PER',
    'PH': 'PHL',
    'PN': 'PCN',
    'PL': 'POL',
    'PT': 'PRT',
    'PR': 'PRI',
    'QA': 'QAT',
    'RE': 'REU',
    'RO': 'ROU',
    'RU': 'RUS',
    'RW': 'RWA',
    'BL': 'BLM',
    'SH': 'SHN',
    'KN': 'KNA',
    'LC': 'LCA',
    'MF': 'MAF',
    'PM': 'SPM',
    'VC': 'VCT',
    'WS': 'WSM',
    'SM': 'SMR',
    'ST': 'STP',
    'SA': 'SAU',
    'SN': 'SEN',
    'RS': 'SRB',
    'SC': 'SYC',
    'SL': 'SLE',
    'SG': 'SGP',
    'SX': 'SXM',
    'SK': 'SVK',
    'SI': 'SVN',
    'SB': 'SLB',
    'SO': 'SOM',
    'ZA': 'ZAF',
    'GS': 'SGS',
    'SS': 'SSD',
    'ES': 'ESP',
    'LK': 'LKA',
    'SD': 'SDN',
    'SR': 'SUR',
    'SJ': 'SJM',
    'SE': 'SWE',
    'CH': 'CHE',
    'SY': 'SYR',
    'TW': 'TWN',
    'TJ': 'TJK',
    'TZ': 'TZA',
    'TH': 'THA',
    'TL': 'TLS',
    'TG': 'TGO',
    'TK': 'TKL',
    'TO': 'TON',
    'TT': 'TTO',
    'TN': 'TUN',
    'TR': 'TUR',
    'TM': 'TKM',
    'TC': 'TCA',
    'TV': 'TUV',
    'UG': 'UGA',
    'UA': 'UKR',
    'AE': 'ARE',
    'GB': 'GBR',
    'US': 'USA',
    'UM': 'UMI',
    'UY': 'URY',
    'UZ': 'UZB',
    'VU': 'VUT',
    'VE': 'VEN',
    'VN': 'VNM',
    'VG': 'VGB',
    'VI': 'VIR',
    'WF': 'WLF',
    'EH': 'ESH',
    'YE': 'YEM',
    'ZM': 'ZMB',
    'ZW': 'ZWE',
}
