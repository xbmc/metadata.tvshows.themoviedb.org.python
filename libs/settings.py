import xbmcaddon, six

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
LANG = ADDON_SETTINGS.getSettingString('language')
CERT_COUNTRY = ADDON_SETTINGS.getSettingString('tmdbcertcountry').lower()
CERT_PREFIX = ADDON_SETTINGS.getSettingString('certprefix')

FANARTTV_CLIENTKEY = ADDON_SETTINGS.getSettingString('fanarttv_clientkey')
FANARTTV_ART = {}
for fanarttv_type, tmdb_type in six.iteritems(FANARTTV_MAPPING):
    FANARTTV_ART[tmdb_type] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_%s' % tmdb_type)

