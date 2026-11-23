"""Kodi 23: a failure told to Kodi, which reports it and tries the look-up again."""
import json
import unittest

from test.unittests.kodi_stubs import Addon

NFO = '<tvshow><title>Test Show</title></tvshow>\nhttps://www.imdb.com/title/tt0000100/'


def guide(**ids):
    return json.dumps(dict({'tmdb': '100'}, **ids))


class TestKodi23(unittest.TestCase):
    def setUp(self):
        self.addon = Addon(self)
        self.failing = self.addon.sites.failing
        self.asked = self.addon.sites.asked

    def test_a_failed_search(self):
        self.failing['search'] = 1
        self.assertEqual(self.addon.call('find', title='Test Show'),
                         {'succeeded': False, 'items': [], 'listitems': []})

    def test_a_search_that_finds_nothing(self):
        self.assertTrue(self.addon.call('find', title='Nothing')['succeeded'])

    def test_a_failed_nfo_lookup(self):
        self.failing['find'] = 1
        self.assertFalse(self.addon.call('NfoUrl', nfo=NFO)['succeeded'])

    def test_a_failed_episode_list(self):
        self.failing['all_seasons'] = 1
        self.assertFalse(self.addon.call('getepisodelist', url=guide())['succeeded'])

    def test_a_failed_episode_group(self):
        self.failing['group'] = 1
        self.assertFalse(self.addon.call('getepisodelist', url=guide(ep_group='g1'))['succeeded'])


if __name__ == '__main__':
    unittest.main()
