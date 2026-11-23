"""Stand-ins for Kodi's python modules and script.module.imdbratings, and for TMDB, Fanart.tv and
Trakt answering the add-on's requests, to run the add-on's calls in a test."""
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
import types
import unittest.mock as mock
from urllib.parse import parse_qsl, urlsplit

ADDON = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DEFAULTS = {'languageDetails': 'en-US', 'ratings': 'TMDb', 'enable_fanarttv': True,
            'tmdbanyway': True, 'imdbanyway': False, 'traktanyway': False, 'verboselog': True,
            'fanarttv_clientkey': ''}


class Recorder:
    """A ListItem's video tag: keeps every setter's last arguments, and lists of add* calls"""

    def __init__(self):
        self.calls = {}

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)

        def record(*args, **kwargs):
            if name.startswith('add'):
                self.calls.setdefault(name, []).append((args, kwargs))
            elif name == 'setRating':
                self.calls.setdefault('setRating', {})[args[2]] = args
            else:
                self.calls[name] = args if len(args) != 1 else args[0]
        return record


class ListItem:
    def __init__(self, label='', offscreen=False):
        self.label = label
        self.tag = Recorder()
        self.properties = {}

    def getVideoInfoTag(self):
        return self.tag

    def setProperty(self, key, value):
        self.properties[key] = value

    def __getattr__(self, name):
        if name.startswith('set'):
            return lambda *a, **k: None
        raise AttributeError(name)


class Actor:
    def __init__(self, name, role, order, thumb):
        self.name, self.role, self.order, self.thumb = name, role, order, thumb


class Kodi:
    """Kodi's modules and script.module.imdbratings, stood in for, and what the add-on did"""

    def __init__(self, settings, profile):
        self.logs, self.results, self.items = [], [], {}
        self.waits = []  # the seconds of each Monitor.waitForAbort()
        self.settings = dict(DEFAULTS, **settings)
        self.profile = profile
        self.abort = False
        # script.module.imdbratings' store: its ratings, whether a dataset is loaded, and what
        # refresh() does
        self.imdb = {'ratings': {}, 'loaded': True, 'refresh': None}

    def logged(self, text):
        return any(text in msg for _, msg in self.logs)

    def modules(self):
        kodi = self
        xbmc = types.ModuleType('xbmc')
        xbmc.LOGDEBUG, xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 0, 1, 2, 3
        xbmc.log = lambda msg, level=0: kodi.logs.append((level, msg))
        xbmc.Actor = Actor

        def wait_for_abort(seconds=0):
            kodi.waits.append(seconds)  # not waited
            return kodi.abort

        xbmc.Monitor = lambda: types.SimpleNamespace(waitForAbort=wait_for_abort,
                                                     abortRequested=lambda: kodi.abort)
        xbmcgui = types.ModuleType('xbmcgui')
        xbmcgui.ListItem = ListItem
        xbmcplugin = types.ModuleType('xbmcplugin')

        def end_of_directory(handle, succeeded=True, *a, **k):
            kodi.results.append(('dir', succeeded, kodi.items.pop(handle, [])))

        xbmcplugin.endOfDirectory = end_of_directory
        xbmcplugin.addDirectoryItem = lambda handle, url, listitem, isFolder=False, *a, **k: \
            kodi.items.setdefault(handle, []).append((url, listitem)) or True
        xbmcplugin.setResolvedUrl = lambda handle, succeeded, listitem: kodi.results.append(
            ('resolved', succeeded, listitem))
        xbmcaddon = types.ModuleType('xbmcaddon')

        class Addon:
            def __init__(self, *a):
                pass

            def getAddonInfo(self, key):
                return {'id': 'metadata.tvshows.themoviedb.org.python',
                        'profile': kodi.profile, 'path': ADDON}.get(key, '')

            def getSetting(self, key):
                value = kodi.settings.get(key, '')
                return value if isinstance(value, str) else str(value).lower()

            def getSettingBool(self, key):
                if key not in kodi.settings:
                    raise RuntimeError(key)  # as Kodi does for a setting it hasn't: the default
                return bool(kodi.settings[key])

            def getSettingInt(self, key):
                return int(kodi.settings.get(key, 0) or 0)

        xbmcaddon.Addon = Addon
        xbmcvfs = types.ModuleType('xbmcvfs')
        xbmcvfs.translatePath = lambda path: path
        imdbratings = types.ModuleType('imdbratings')
        imdbratings.get_rating = lambda imdb_id: (
            kodi.imdb['ratings'].get(imdb_id) if kodi.imdb['loaded'] else None)
        imdbratings.dataset_date = lambda: '2026-11-14' if kodi.imdb['loaded'] else None
        imdbratings.refresh = lambda abort=None, on_download=None: (
            kodi.imdb['refresh']() if kodi.imdb['refresh'] else False)
        return {m.__name__: m for m in (xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs, imdbratings)}


# ---------------------------------------------------------------- TMDB, Fanart.tv and Trakt

def _person(name, order):
    return {'name': name, 'character': name + ' role', 'order': order, 'profile_path': None}


def _image(path, lang='en'):
    return {'file_path': path, 'iso_639_1': lang, 'width': 1000, 'height': 1500,
            'vote_average': 5.0, 'vote_count': 1}


def _show(show_id):
    """The shows: 100, 101 and 103 have seasons 0 (2 episodes), 1 (12) and 2 (3); 101 has a
    Fanart.tv id that Fanart.tv hasn't, and is on IMDb but not on Trakt; 102 has no IMDb id;
    103 has no season regulars; 300 has seasons 1 to 22 of one episode each"""
    if show_id in (100, 101, 102, 103):
        seasons = {0: 2, 1: 12, 2: 3}
    elif show_id == 300:
        seasons = {n: 1 for n in range(1, 23)}
    else:
        return None
    return {
        'id': show_id, 'name': 'Test Show', 'original_name': 'Test Show', 'overview': 'A plot.',
        'first_air_date': '2010-01-01',
        'seasons': [{'season_number': n, 'name': 'Season {}'.format(n), 'overview': '',
                     'episode_count': count} for n, count in seasons.items()],
        '_episodes': seasons,
        'external_ids': {'imdb_id': {100: 'tt0000100', 101: 'tt0000101', 103: 'tt0000103',
                                     300: 'tt0000300'}.get(show_id, ''),
                         'tvdb_id': {100: 500, 101: 501, 102: 502, 103: 504, 300: 503}[show_id]},
        'vote_average': 7.5, 'vote_count': 100, 'genres': [], 'networks': [],
        'origin_country': ['US'], 'status': 'Ended', 'episode_run_time': [30],
        'created_by': [], 'spoken_languages': [],
    }


def _episode(show_id, season, number, language):
    name = 'Episode {}'.format(number) if language == 'de-DE' else 'Ep {}.{}'.format(season, number)
    return {'id': show_id * 100000 + season * 1000 + number, 'season_number': season,
            'episode_number': number, 'name': name,
            'overview': '' if language == 'de-DE' else 'Overview {}.{}'.format(season, number),
            'air_date': '2010-01-01', 'crew': [], 'guest_stars': [], 'vote_average': 7.0,
            'vote_count': 5, 'runtime': 30}


def _season(show, number, language):
    return {'season_number': number,
            'episodes': [_episode(show['id'], number, e, language)
                         for e in range(1, show['_episodes'][number] + 1)]}


def _tv(show_id, rest, q):
    show = _show(show_id)
    if show is None:
        return None
    language = q.get('language', 'en-US')
    if rest == '/aggregate_credits':
        return {'cast': [{'name': 'Guest {}'.format(i), 'roles': [{'character': 'c'}],
                          'profile_path': None} for i in range(1, 31)]}
    m = re.match(r'/season/(\d+)/episode/(\d+)$', rest)
    if m:
        season, number = int(m.group(1)), int(m.group(2))
        if season not in show['_episodes'] or number > show['_episodes'][season]:
            return None
        ep = _episode(show_id, season, number, language)
        ep['images'] = {'stills': [_image('/single{}_{}.jpg'.format(season, number))]}
        ep['external_ids'] = {'imdb_id': 'tt9{:02}{:02}'.format(season, number)}
        return ep
    m = re.match(r'/season/(\d+)$', rest)
    if m:
        return _season(show, int(m.group(1)), language) if int(m.group(1)) in show['_episodes'] else None
    data = {k: v for k, v in show.items() if not k.startswith('_')}
    if language == 'de-DE':
        data['overview'] = ''
    for key in filter(None, q.get('append_to_response', '').split(',')):
        if key == 'credits':
            data['credits'] = {'cast': [_person('Reg A', 0), _person('Reg B', 1)], 'crew': []}
        elif key == 'images':
            data['images'] = {'posters': [_image('/poster.jpg')], 'backdrops': [_image('/back.jpg', None)]}
        elif key in ('content_ratings', 'videos', 'keywords'):
            data[key] = {'results': []}
        elif key == 'external_ids':
            pass
        else:
            m = re.match(r'season/(\d+)(?:/(images|credits)|/episode/(\d+)/(images|external_ids))?$', key)
            season = int(m.group(1))
            if season not in show['_episodes']:
                continue  # as TMDB does for a season it hasn't
            if m.group(2) == 'images':
                data[key] = {'posters': [_image('/season{}.jpg'.format(season))], 'backdrops': []}
            elif m.group(2) == 'credits':
                cast = [_person('Reg A', 0), _person('Reg B', 1)]
                if season == 1:
                    cast.append(_person('Reg C', 2))
                data[key] = {'cast': [] if show_id == 103 else cast}
            elif m.group(4) == 'images':
                data[key] = {'stills': [_image('/still{}_{}.jpg'.format(season, m.group(3)))]}
            elif m.group(4) == 'external_ids':
                data[key] = {'imdb_id': 'tt8{:02}{:02}'.format(season, int(m.group(3)))}
            else:
                data[key] = _season(show, season, language)
    return data


def _answer(path, q):
    """The JSON a site answers, or None for a 404"""
    if path.startswith('/3/'):
        p = path[2:]
        if p == '/configuration':
            return {'images': {'secure_base_url': 'https://image.tmdb.org/t/p/'}}
        if p == '/search/tv':
            hit = {'id': 100, 'name': 'Test Show', 'original_name': 'Test Show',
                   'first_air_date': '2010-01-01', 'origin_country': ['US'], 'overview': '',
                   'poster_path': '/p.jpg', 'popularity': 10.0}
            return {'results': [hit] if q.get('query', '').lower() == 'test show' else []}
        if p.startswith('/find/'):
            return {'tv_results': [{'id': 100}] if p == '/find/tt0000100' else []}
        if p.startswith('/tv/episode_group/'):
            if p.endswith('/g1'):
                return {'groups': [{'order': 1, 'episodes': [
                    {'season_number': 1, 'episode_number': e, 'order': 12 - e} for e in range(1, 13)]}]}
            if p.endswith('/same'):
                # numbered as aired: only its being a group's tells it apart
                return {'groups': [{'order': 1, 'episodes': [
                    {'season_number': 1, 'episode_number': 1, 'order': 0}]}]}
            return None
        m = re.match(r'/tv/(\d+)(/.*)?$', p)
        return _tv(int(m.group(1)), m.group(2) or '', q) if m else None
    if path.startswith('/fanart/tv/'):
        if path.endswith(('/500', '/503', '/504')):
            return {'tvposter': [{'url': 'https://assets.fanart.tv/fanart/tv/a.jpg', 'lang': 'en', 'likes': '1'}],
                    'seasonposter': [{'url': 'https://assets.fanart.tv/fanart/tv/s1.jpg', 'lang': 'en',
                                      'likes': '1', 'season': '1'}]}
        return None
    if path.startswith('/trakt/shows/'):
        if not any(imdb_id in path for imdb_id in ('tt0000100', 'tt0000103', 'tt0000300')):
            return None
        if '/episodes/' in path:
            return {'rating': 6.5, 'votes': 10}
        if '/seasons/' in path:
            return [{'number': e, 'rating': 7.25, 'votes': 10} for e in range(1, 13)]
        return {'rating': 8.0, 'votes': 100}
    return None


def _kind(path, q):
    """The kind of request, for Sites.asked and Sites.failing"""
    if path.startswith('/3/'):
        p = path[2:]
        app = q.get('append_to_response', '')
        if p == '/search/tv':
            return 'search'
        if p.startswith('/find/'):
            return 'find'
        if p == '/configuration':
            return 'config'
        if p.startswith('/tv/episode_group/'):
            return 'group'
        m = re.match(r'/tv/(\d+)(/.*)?$', p)
        rest = (m.group(2) or '') if m else ''
        if rest == '/aggregate_credits':
            return 'aggregate'
        if '/episode/' in rest:
            return 'episode'
        if rest.startswith('/season/'):
            return 'season_en'
        if '/episode/' in app:
            return 'episode_extras'
        if re.search(r'season/\d+/images', app):
            return 'season_data'
        if 'season/' in app:
            return 'all_seasons_2' if 'season/21' in app else 'all_seasons'
        return 'show' if app else 'show_en'
    if path.startswith('/fanart/'):
        return 'fanart'
    if '/episodes/' in path:
        return 'trakt_episode'
    return 'trakt_season' if '/seasons/' in path else 'trakt_show'


class Sites:
    """TMDB, Fanart.tv and Trakt, answering get_json(): asked counts the requests of each kind,
    failing[kind] = n makes the next n of them fail (raise RequestFailed, after their retry)"""

    def __init__(self, request_failed):
        self.asked, self.failing = {}, {}
        self.request_failed = request_failed

    def get_json(self, url, headers, label):
        parts = urlsplit(url)
        path = {'webservice.fanart.tv': '/fanart' + parts.path[len('/v3.2'):],
                'api.trakt.tv': '/trakt' + parts.path}.get(parts.hostname, parts.path)
        q = dict(parse_qsl(parts.query))
        kind = _kind(path, q)
        self.asked[kind] = self.asked.get(kind, 0) + 1
        if self.failing.get(kind):
            self.failing[kind] -= 1
            raise self.request_failed('{} failed: a stand-in failure'.format(label))
        data = _answer(path, q)
        return None if data is None else json.loads(json.dumps(data))


class Addon:
    """The add-on, imported afresh for a test, with Kodi's modules stood in for"""

    def __init__(self, test, settings=None, fake_sites=True):
        profile = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, profile, True)
        self.kodi = Kodi(settings or {}, profile)
        modules = mock.patch.dict(sys.modules, self.kodi.modules())
        modules.start()
        test.addCleanup(modules.stop)
        # the handle, and a query without path settings
        argv = mock.patch.object(sys, 'argv', ['plugin://' + __name__, '1', ''])
        argv.start()
        test.addCleanup(argv.stop)
        for name in [n for n in sys.modules if n in ('lib', 'main') or n.startswith('lib.')]:
            del sys.modules[name]  # the patch puts them back
        sys.path.insert(0, ADDON)
        test.addCleanup(sys.path.remove, ADDON)
        self.scraper = importlib.import_module('lib.scraper')
        self.request = importlib.import_module('lib.api.request')
        test.addCleanup(self.request.SESSION.close)
        self.tmdb = importlib.import_module('lib.api.tmdb')
        self.sites = Sites(self.request.RequestFailed)
        if fake_sites:
            for name in ('lib.api.tmdb', 'lib.api.trakt', 'lib.api.fanarttv'):
                patch = mock.patch.object(sys.modules[name], 'get_json', side_effect=self.sites.get_json)
                patch.start()
                test.addCleanup(patch.stop)

    @property
    def cache(self):
        return self.tmdb._cache

    def call(self, action, **params):
        """scraper.run_action() for a call, and what it told Kodi"""
        before = len(self.kodi.results)
        self.scraper.run_action(1, action, dict(params, action=action))
        assert len(self.kodi.results) == before + 1, 'the call told Kodi {} things'.format(
            len(self.kodi.results) - before)
        kind, succeeded, payload = self.kodi.results[-1]
        if kind == 'dir':
            return {'succeeded': succeeded, 'items': [url for url, _ in payload],
                    'listitems': [item for _, item in payload]}
        calls = payload.tag.calls
        art = calls.get('addAvailableArtwork', [])
        return {'succeeded': succeeded,
                'cast': [a.name for a in calls.get('setCast', [])],
                'ratings': {k: v[0] for k, v in calls.get('setRating', {}).items()},
                'plot': calls.get('setPlot'),
                'season posters': len([a for a in art if 'season' in a[1] and a[1]['arttype'] == 'poster'
                                       and 'fanart.tv' not in a[0][0]]),  # TMDB's
                'fanart.tv art': len([a for a in art if 'fanart.tv' in a[0][0]]),
                'stills': [a[0][0].rsplit('/', 1)[-1] for a in art if a[1].get('arttype') == 'thumb']}
