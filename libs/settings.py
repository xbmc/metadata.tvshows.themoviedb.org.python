import xbmcaddon, six

TMDB_CLOWNCAR = 'af3a53eb387d57fc935e9128468b1899'
FANARTTV_CLOWNCAR = 'b018086af0e1478479adfc55634db97d'
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

ADDON_SETTINGS = xbmcaddon.Addon()
KEEPTITLE = ADDON_SETTINGS.getSettingBool('keeporiginaltitle')
VERBOSELOG = ADDON_SETTINGS.getSettingBool('verboselog')
LANG = ADDON_SETTINGS.getSettingString('language').replace('-', '_')
CERT_COUNTRY = ADDON_SETTINGS.getSettingString('tmdbcertcountry').lower()

if ADDON_SETTINGS.getSettingBool('usecertprefix'):
    CERT_PREFIX = ADDON_SETTINGS.getSettingString('certprefix')
else:
    CERT_PREFIX = ''

primary_rating = ADDON_SETTINGS.getSettingString('ratings').lower()
RATING_TYPES = [primary_rating]
if ADDON_SETTINGS.getSettingBool('imdbanyway') and primary_rating != 'imdb':
    RATING_TYPES.append('imdb')
if ADDON_SETTINGS.getSettingBool('traktanyway') and primary_rating != 'trakt':
    RATING_TYPES.append('trakt')
if ADDON_SETTINGS.getSettingBool('tmdbanyway') and primary_rating != 'tmdb':
    RATING_TYPES.append('tmdb')

FANARTTV_CLIENTKEY = ADDON_SETTINGS.getSettingString('fanarttv_clientkey')
FANARTTV_ART = {}
for fanarttv_type, tmdb_type in six.iteritems(FANARTTV_MAPPING):
    FANARTTV_ART[tmdb_type] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_%s' % tmdb_type)

