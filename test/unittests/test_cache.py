"""What an interpreter keeps of the shows it was asked for: the episodes of the last shows used, a
while, and the shows' details."""
import json
import time
import unittest

from test.unittests.kodi_stubs import Addon


def guide(show_id):
    return json.dumps({'tmdb': show_id})


class TestEpisodesKept(unittest.TestCase):
    def setUp(self):
        self.addon = Addon(self)
        self.tmdb = self.addon.tmdb
        self.cache = self.addon.cache

    def test_the_most_recently_used_keep_their_episodes(self):
        now = time.time()
        kept = self.tmdb._EPISODES_KEPT
        for i in range(1, kept + 3):  # used in that order, show 2 an hour ago
            self.cache[str(i)] = {'show': {'id': i}, 'episodes': {(1, 1): {}},
                                  'used': now - 3600 if i == 2 else now - 60 + i}
        self.tmdb.evict_episodes()
        self.assertEqual([k for k, v in self.cache.items() if 'episodes' in v],
                         [str(i) for i in range(3, kept + 3)])
        self.assertTrue(all('show' in v for v in self.cache.values()))

    def test_episodes_unused_a_while_are_dropped(self):
        now = time.time()
        self.cache['7'] = {'episodes': {}, 'used': now - self.tmdb._EPISODES_TTL - 1}
        self.cache['8'] = {'episodes': {}, 'used': now}
        self.tmdb.evict_episodes()
        self.assertNotIn('episodes', self.cache['7'])
        self.assertIn('episodes', self.cache['8'])

    def test_another_shows_details_keep_the_guide(self):
        # A scan can look up the shows ahead before it asks for the episodes of the one before
        self.addon.call('getdetails', url='100')
        self.addon.call('getepisodelist', url=guide('100'))
        self.addon.call('getdetails', url='101')
        self.addon.call('getepisodelist', url=guide('101'))
        asked = dict(self.addon.sites.asked)
        for number in range(1, 13):
            self.assertTrue(self.addon.call('getepisodedetails',
                                            url='100/1/{}'.format(number))['succeeded'])
        self.assertEqual(self.addon.sites.asked, asked)  # all from the guides kept

    def test_episodes_on_an_interpreter_without_the_guide(self):
        # Kodi can run a show's calls on any of its interpreters: each episode is asked for alone,
        # and the show only when the Trakt rating needs its IMDb id
        for number in range(1, 13):
            self.assertTrue(self.addon.call('getepisodedetails',
                                            url='100/1/{}'.format(number))['succeeded'])
        self.assertEqual(self.addon.sites.asked, {'episode': 12, 'config': 1})
        self.assertNotIn('episodes', self.cache.get('100', {}))  # one episode isn't a guide
        listed = self.addon.call('getepisodelist', url=guide('100'))
        self.assertEqual(len(listed['items']), 17)


if __name__ == '__main__':
    unittest.main()
