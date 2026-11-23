"""A request that still fails after its retry: the call fails when it was for the show, its episode
list or an episode, and a part of the details is left out and logged, and asked for again."""
import json
import unittest

from test.unittests.kodi_stubs import Addon

NFO = '<tvshow><title>Test Show</title></tvshow>\nhttps://www.imdb.com/title/tt0000100/'


def guide(**ids):
    return json.dumps(dict({'tmdb': '100'}, **ids))


class TestFailures(unittest.TestCase):
    def setUp(self):
        self.addon = Addon(self)
        self.failing = self.addon.sites.failing
        self.asked = self.addon.sites.asked

    def assertLogged(self, text):
        self.assertTrue(self.addon.kodi.logged(text), text)

    # ---------------------------------------------------------------- listings

    def test_search(self):
        self.failing['search'] = 1
        found = self.addon.call('find', title='Test Show')
        self.assertEqual(found['items'], [])
        self.assertLogged('find failed: TMDB GET /search/tv failed')

    def test_nfo_find(self):
        self.failing['find'] = 1
        found = self.addon.call('NfoUrl', nfo=NFO)
        self.assertEqual(found['items'], [])
        self.assertLogged('NfoUrl failed:')

    def test_episode_list_and_asked_again(self):
        self.failing['all_seasons_2'] = 1
        listed = self.addon.call('getepisodelist', url=guide(tmdb='300'))
        self.assertEqual(listed['items'], [])
        self.assertNotIn('episodes', self.addon.cache.get('300', {}))  # nothing of it kept
        self.assertLogged('getepisodelist failed:')
        self.assertEqual(len(self.addon.call('getepisodelist', url=guide(tmdb='300'))['items']), 22)

    def test_episode_group(self):
        self.failing['group'] = 1
        self.assertEqual(self.addon.call('getepisodelist', url=guide(ep_group='g1'))['items'], [])

    def test_episode_group_tmdb_hasnt(self):
        listed = self.addon.call('getepisodelist', url=guide(ep_group='gone'))
        self.assertEqual(len(listed['items']), 17)  # in aired order
        self.assertLogged('episode group gone not found')

    # ---------------------------------------------------------------- a show's details

    def test_show(self):
        self.failing['show'] = 1
        self.assertFalse(self.addon.call('getdetails', url='100')['succeeded'])
        self.assertLogged('getdetails failed: TMDB GET /tv/100 failed')

    def test_seasons_images_and_cast(self):
        self.failing['season_data'] = 1
        show = self.addon.call('getdetails', url='100')
        self.assertTrue(show['succeeded'])
        self.assertEqual(show['season posters'], 0)  # TMDB's
        # the show's own cast: without the seasons' the whole run's isn't asked for
        self.assertEqual(show['cast'], ['Reg A', 'Reg B'])
        self.assertEqual(self.asked.get('aggregate', 0), 0)
        self.assertLogged('the images and cast of seasons [0, 1, 2] left out')
        self.assertNotIn('100', self.addon.cache)  # not kept: the next call asks again
        show = self.addon.call('getdetails', url='100')
        self.assertEqual(show['cast'], ['Reg A', 'Reg B', 'Reg C'])
        self.assertIn('show', self.addon.cache['100'])

    def test_whole_runs_cast(self):
        self.failing['aggregate'] = 1
        show = self.addon.call('getdetails', url='103')
        self.assertTrue(show['succeeded'])
        self.assertEqual(show['cast'], ['Reg A', 'Reg B'])  # the show's own
        self.assertLogged("the show's cast left out")
        self.assertNotIn('103', self.addon.cache)

    def test_english_overview(self):
        addon = Addon(self, {'languageDetails': 'de-DE'})
        addon.sites.failing['show_en'] = 1
        show = addon.call('getdetails', url='100')
        self.assertTrue(show['succeeded'])
        self.assertEqual(show['plot'], '')
        self.assertTrue(addon.kodi.logged('the English overview left out'))
        self.assertNotIn('100', addon.cache)
        self.assertEqual(addon.call('getdetails', url='100')['plot'], 'A plot.')

    def test_fanarttv(self):
        self.failing['fanart'] = 1
        show = self.addon.call('getdetails', url='100')
        self.assertTrue(show['succeeded'])
        self.assertEqual(show['fanart.tv art'], 0)
        self.assertLogged("fanart.tv's art left out")
        self.assertGreater(self.addon.call('getartwork', id='100')['fanart.tv art'], 0)
        self.assertEqual(self.asked['fanart'], 2)  # asked again
        self.addon.call('getdetails', url='100')
        self.assertEqual(self.asked['fanart'], 2)  # and only then

    def test_art_left_out_isnt_kept_on_disk(self):
        # where getartwork on another interpreter would take it as it is
        for kind in ('fanart', 'season_data'):
            with self.subTest(kind=kind):
                addon = Addon(self)
                addon.sites.failing[kind] = 1
                self.assertTrue(addon.call('getdetails', url='100')['succeeded'])
                self.assertIsNone(addon.scraper.art_cache.load('100'))
                addon.call('getdetails', url='100')
                self.assertIsNotNone(addon.scraper.art_cache.load('100'))

    def test_fanarttv_hasnt_the_show(self):
        self.addon.call('getdetails', url='101')
        self.addon.call('getartwork', id='101')
        self.assertEqual(self.asked['fanart'], 1)  # a 404 is an answer

    def test_trakt(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        addon.sites.failing['trakt_show'] = 1
        show = addon.call('getdetails', url='100')
        self.assertTrue(show['succeeded'])
        self.assertNotIn('trakt', show['ratings'])
        self.assertTrue(addon.kodi.logged('the Trakt rating left out'))

    def test_artwork(self):
        self.failing['show'] = 1
        self.assertFalse(self.addon.call('getartwork', id='100')['succeeded'])

    # ---------------------------------------------------------------- an episode's details

    def test_episodes_images_and_ids(self):
        self.failing['episode_extras'] = 1
        listed = self.addon.call('getepisodelist', url=guide())
        self.assertEqual(len(listed['items']), 17)  # the guide is whole without them
        episode = self.addon.call('getepisodedetails', url='100/0/1')
        self.assertTrue(episode['succeeded'])
        self.assertEqual(episode['stills'], ['single0_1.jpg'])  # asked for with the episode
        self.assertEqual(self.asked['episode'], 1)

    def test_episodes_images_and_ids_and_the_episode(self):
        self.failing['episode_extras'] = 1
        self.failing['episode'] = 1
        self.addon.call('getepisodelist', url=guide())
        self.assertFalse(self.addon.call('getepisodedetails', url='100/0/1')['succeeded'])
        self.assertLogged('getepisodedetails failed:')

    def test_episode(self):
        self.failing['episode'] = 1
        self.assertFalse(self.addon.call('getepisodedetails', url='100/1/3')['succeeded'])

    def test_episodes_english_text(self):
        addon = Addon(self, {'languageDetails': 'de-DE'})
        addon.sites.failing['season_en'] = 1
        listed = addon.call('getepisodelist', url=guide())
        self.assertEqual(len(listed['items']), 17)
        self.assertTrue(addon.kodi.logged('the English text of season'))
        self.assertIn('episodes', addon.cache['100'])  # kept: it would cost a request an episode

    def test_trakt_seasons(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        addon.sites.failing['trakt_season'] = 1
        self.assertEqual(len(addon.call('getepisodelist', url=guide())['items']), 17)
        episode = addon.call('getepisodedetails', url='100/0/1')
        self.assertEqual(episode['ratings'].get('trakt'), 6.5)  # its own, asked for instead

    def test_trakt_episode(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        addon.sites.failing['trakt_episode'] = 1
        episode = addon.call('getepisodedetails', url='100/1/3')
        self.assertTrue(episode['succeeded'])
        self.assertNotIn('trakt', episode['ratings'])
        self.assertTrue(addon.kodi.logged('the Trakt rating left out'))

    def test_show_for_the_trakt_rating(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        addon.sites.failing['show'] = 1
        episode = addon.call('getepisodedetails', url='100/1/3')
        self.assertTrue(episode['succeeded'])
        self.assertNotIn('trakt', episode['ratings'])
        self.assertTrue(addon.kodi.logged('the Trakt rating left out: TMDB GET /tv/100 failed'))


if __name__ == '__main__':
    unittest.main()
