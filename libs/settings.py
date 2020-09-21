import xbmcaddon

ADDON_SETTINGS = xbmcaddon.Addon()
LANG = ADDON_SETTINGS.getSettingString('language')
CERT_COUNTRY = ADDON_SETTINGS.getSettingString('tmdbcertcountry').lower()
CERT_PREFIX = ADDON_SETTINGS.getSettingString('certprefix')

FANARTTV_CLIENTKEY = ADDON_SETTINGS.getSettingString('fanarttv_clientkey')
FANARTTV_ART = {}
FANARTTV_ART['showbackground'] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_fanart')
FANARTTV_ART['tvposter'] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_poster')
FANARTTV_ART['tvbanner'] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_banner')
FANARTTV_ART['hdtvlogo'] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_clearlogo')
FANARTTV_ART['hdclearart'] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_clearart')
FANARTTV_ART['seasonposter'] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_seasonposter')
FANARTTV_ART['seasonbanner'] = ADDON_SETTINGS.getSettingBool('enable_fanarttv_seasonbanner')

IMAGEROOTURL = 'https://image.tmdb.org/t/p/original'