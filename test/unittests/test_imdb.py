"""IMDb ratings from script.module.imdbratings, which the stand-in's store gives."""
import json
import os
import sys
import unittest

from test.unittests.kodi_stubs import Addon


class TestImdbRatings(unittest.TestCase):
    def setUp(self):
        self.addon = Addon(self, {'ratings': 'IMDb'})
        self.store = self.addon.kodi.imdb
        self.module = sys.modules['imdbratings']

    def test_rating(self):
        self.store['ratings'] = {'tt0000100': (8.1, 5000)}
        show = self.addon.call('getdetails', url='100')
        self.assertEqual(show['ratings'].get('imdb'), 8.1)

    def test_episode_rating(self):
        self.store['ratings'] = {'tt80103': (7.7, 50)}
        self.addon.call('getepisodelist', url=json.dumps({'tmdb': '100'}))
        episode = self.addon.call('getepisodedetails', url='100/1/3')
        self.assertEqual(episode['ratings'].get('imdb'), 7.7)

    def test_not_in_the_dataset(self):
        show = self.addon.call('getdetails', url='100')
        self.assertTrue(show['succeeded'])
        self.assertNotIn('imdb', show['ratings'])
        self.assertFalse(self.addon.kodi.logged('left out'))

    def test_no_wait_of_its_own(self):
        # Waiting for a first load is the module's: the add-on neither refreshes nor waits
        self.store['loaded'] = False
        self.store['refresh'] = lambda: self.fail('refreshed')
        self.addon.call('getdetails', url='100')
        self.assertEqual(self.addon.kodi.waits, [])

    def test_first_load_ending_between_the_reads(self):
        # The dataset is loaded just after the rating is read, and before anything else is: the
        # rating read must not then pass for "no rating"
        self.store.update(loaded=False, ratings={'tt0000100': (8.1, 5000)})
        get_rating = self.module.get_rating

        def read_then_loaded(imdb_id):
            rating = get_rating(imdb_id)
            self.store['loaded'] = True
            return rating
        self.module.get_rating = read_then_loaded
        self.assertEqual(self.addon.call('getdetails', url='100')['ratings'].get('imdb'), 8.1)

    def test_show_without_an_imdb_id(self):
        self.store['loaded'] = False
        self.store['refresh'] = lambda: self.fail('looked up')
        show = self.addon.call('getdetails', url='102')
        self.assertTrue(show['succeeded'])
        self.assertFalse(self.addon.kodi.logged('left out'))

    def test_the_old_store_is_removed(self):
        old = os.path.join(self.addon.kodi.profile, 'imdb_ratings.db')
        open(old, 'w').close()
        self.addon.call('getdetails', url='100')
        self.assertFalse(os.path.exists(old))


if __name__ == '__main__':
    unittest.main()
