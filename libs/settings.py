import json, six, sys
from six.moves import urllib_parse
from .utils import logger
from pprint import pformat


TMDB_CLOWNCAR = 'af3a53eb387d57fc935e9128468b1899'
FANARTTV_CLOWNCAR = 'b018086af0e1478479adfc55634db97d'
TRAKT_CLOWNCAR = '90901c6be3b2de5a4fa0edf9ab5c75e9a5a0fef2b4ee7373d8b63dcf61f95697'
MAXIMAGES = 350
IMAGEROOTURL = 'https://image.tmdb.org/t/p/original'
FANARTTV_MAPPING = { 'showbackground': 'backdrops',
                     'tvposter': 'posters',
                     'tvbanner': 'banner',
                     'hdtvlogo': 'clearlogo',
                     'clearlogo': 'clearlogo',
                     'hdclearart': 'clearart',
                     'clearart': 'clearart',
                     'tvthumb': 'landscape',
                     'characterart': 'characterart',
                     'seasonposter':'seasonposters',
                     'seasonbanner':'seasonbanner',
                     'seasonthumb': 'seasonlandscape'
                   }
try:
    source_params = dict(urllib_parse.parse_qsl(sys.argv[2]))
except IndexError:
    source_params = {}
source_settings = json.loads(source_params.get('pathSettings', {}))
logger.debug('the source settings are:\n{}'.format(pformat(source_settings)))

KEEPTITLE =source_settings.get('keeporiginaltitle', False)
VERBOSELOG =  source_settings.get('verboselog', False)
LANG = source_settings.get('language', 'en-US')
CERT_COUNTRY = source_settings.get('tmdbcertcountry', 'us').lower()

if source_settings.get('usecertprefix', True):
    CERT_PREFIX = source_settings.get('certprefix', 'Rated ')
else:
    CERT_PREFIX = ''
primary_rating = source_settings.get('ratings', 'TMDb').lower()
RATING_TYPES = [primary_rating]
if source_settings.get('imdbanyway', False) and primary_rating != 'imdb':
    RATING_TYPES.append('imdb')
if source_settings.get('traktanyway', False) and primary_rating != 'trakt':
    RATING_TYPES.append('trakt')
if source_settings.get('tmdbanyway', False) and primary_rating != 'tmdb':
    RATING_TYPES.append('tmdb')
FANARTTV_CLIENTKEY = source_settings.get('fanarttv_clientkey', '')
FANARTTV_ART = {}
for fanarttv_type, tmdb_type in six.iteritems(FANARTTV_MAPPING):
    FANARTTV_ART[tmdb_type] = source_settings.get('enable_fanarttv_%s' % tmdb_type, False)
