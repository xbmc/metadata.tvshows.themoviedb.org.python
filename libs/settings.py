import xbmcaddon

ADDON_SETTINGS = xbmcaddon.Addon()
LANG = ADDON_SETTINGS.getSettingString('language')
CERT_COUNTRY = ADDON_SETTINGS.getSettingString('tmdbcertcountry').lower()
CERT_PREFIX = ADDON_SETTINGS.getSettingString('certprefix')
IMAGEROOTURL = 'https://image.tmdb.org/t/p/original'
