"""Kodi's calls to the add-on, each answered from a stand-in TMDB, Fanart.tv and Trakt."""
import json
import unittest

from test.unittests.kodi_stubs import Addon

NFO = '<tvshow><title>Test Show</title></tvshow>\nhttps://www.imdb.com/title/tt0000100/'


def guide(**ids):
    """The episode guide Kodi passes back to getepisodelist"""
    return json.dumps(dict({'tmdb': '100'}, **ids))


class TestCalls(unittest.TestCase):
    def setUp(self):
        self.addon = Addon(self)

    def test_find(self):
        found = self.addon.call('find', title='Test Show', year='2010')
        self.assertEqual((found['succeeded'], found['items']), (True, ['100']))

    def test_find_nothing(self):
        found = self.addon.call('find', title='Nothing')
        self.assertEqual((found['succeeded'], found['items']), (True, []))

    def test_nfo_with_an_imdb_id(self):
        found = self.addon.call('NfoUrl', nfo=NFO)
        self.assertEqual((found['succeeded'], found['items']), (True, ['100']))

    def test_details(self):
        show = self.addon.call('getdetails', url='100')
        self.assertTrue(show['succeeded'])
        self.assertEqual(show['cast'], ['Reg A', 'Reg B', 'Reg C'])  # the seasons' regulars
        self.assertEqual(show['plot'], 'A plot.')
        self.assertEqual(show['season posters'], 3)
        self.assertEqual(self.addon.sites.asked.get('aggregate', 0), 0)
        self.assertGreater(show['fanart.tv art'], 0)
        self.assertIn('show', self.addon.cache['100'])

    def test_details_without_season_regulars(self):
        show = self.addon.call('getdetails', url='103')
        self.assertTrue(show['succeeded'])
        self.assertEqual(len(show['cast']), 30)  # the whole run's
        self.assertEqual(self.addon.sites.asked['aggregate'], 1)

    def test_details_of_a_show_tmdb_hasnt(self):
        show = self.addon.call('getdetails', url='999')
        self.assertFalse(show['succeeded'])
        self.assertEqual(self.addon.sites.asked['show'], 1)

    def test_details_without_fanarttv_art(self):
        self.assertTrue(self.addon.call('getdetails', url='101')['succeeded'])

    def test_episode_list(self):
        listed = self.addon.call('getepisodelist', url=guide())
        self.assertTrue(listed['succeeded'])
        self.assertEqual(len(listed['items']), 17)
        self.assertEqual(listed['items'][:3], ['100/0/1', '100/0/2', '100/1/1'])

    def test_episode_list_in_an_episode_groups_order(self):
        listed = self.addon.call('getepisodelist', url=guide(ep_group='g1'))
        self.assertTrue(listed['succeeded'])
        self.assertEqual(listed['items'][0], '100/1/12')

    def test_episode_details_after_the_list(self):
        self.addon.call('getepisodelist', url=guide())
        before = dict(self.addon.sites.asked)
        episode = self.addon.call('getepisodedetails', url='100/1/3')
        self.assertTrue(episode['succeeded'])
        self.assertEqual(episode['plot'], 'Overview 1.3')
        self.assertEqual(episode['stills'], ['still1_3.jpg'])
        self.assertEqual(self.addon.sites.asked.get('episode', 0), before.get('episode', 0))

    def test_episode_details_alone(self):
        episode = self.addon.call('getepisodedetails', url='100/1/3')
        self.assertTrue(episode['succeeded'])
        self.assertEqual(episode['stills'], ['single1_3.jpg'])
        self.assertEqual(self.addon.sites.asked['episode'], 1)

    def test_episode_details_of_an_episode_tmdb_hasnt(self):
        self.assertFalse(self.addon.call('getepisodedetails', url='100/1/99')['succeeded'])

    def test_artwork(self):
        art = self.addon.call('getartwork', id='100')
        self.assertTrue(art['succeeded'])
        self.assertGreater(art['fanart.tv art'], 0)


class TestRatings(unittest.TestCase):
    def test_trakt(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        show = addon.call('getdetails', url='100')
        self.assertEqual(show['ratings'].get('trakt'), 8.0)
        addon.call('getepisodelist', url=guide())
        episode = addon.call('getepisodedetails', url='100/1/3')
        self.assertEqual(episode['ratings'].get('trakt'), 7.25)  # from the season's, listed

    def test_trakt_hasnt_the_show(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        show = addon.call('getdetails', url='101')
        self.assertTrue(show['succeeded'])
        self.assertNotIn('trakt', show['ratings'])


if __name__ == '__main__':
    unittest.main()
