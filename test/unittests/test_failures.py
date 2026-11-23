"""A request that still fails after its retry, and the call it was for fails. A part of the
details that fails fails the call too: see test_kodi23.py."""
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

    def test_fanarttv_hasnt_the_show(self):
        self.addon.call('getdetails', url='101')
        self.addon.call('getartwork', id='101')
        self.assertEqual(self.asked['fanart'], 1)  # a 404 is an answer

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

    def test_trakt_seasons(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        addon.sites.failing['trakt_season'] = 1
        self.assertEqual(len(addon.call('getepisodelist', url=guide())['items']), 17)
        episode = addon.call('getepisodedetails', url='100/0/1')
        self.assertEqual(episode['ratings'].get('trakt'), 6.5)  # its own, asked for instead



if __name__ == '__main__':
    unittest.main()
