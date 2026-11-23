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

    # ---------------------------------------------------------------- a part that fails

    def assertFailsAndIsAskedAgain(self, addon, call, kind, **params):
        addon.sites.failing[kind] = 1
        self.assertFalse(addon.call(call, **params)['succeeded'])
        self.assertTrue(addon.kodi.logged('{} failed:'.format(call)))
        self.assertFalse(addon.kodi.logged('left out'))
        self.assertTrue(addon.call(call, **params)['succeeded'])

    def test_seasons_images_and_cast(self):
        self.assertFailsAndIsAskedAgain(self.addon, 'getdetails', 'season_data', url='100')

    def test_whole_runs_cast(self):
        self.assertFailsAndIsAskedAgain(self.addon, 'getdetails', 'aggregate', url='103')

    def test_english_overview(self):
        addon = Addon(self, {'languageDetails': 'de-DE'})
        self.assertFailsAndIsAskedAgain(addon, 'getdetails', 'show_en', url='100')

    def test_fanarttv(self):
        self.assertFailsAndIsAskedAgain(self.addon, 'getdetails', 'fanart', url='100')

    def test_fanarttv_for_the_art(self):
        self.assertFailsAndIsAskedAgain(self.addon, 'getartwork', 'fanart', id='100')

    def test_trakt(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        self.assertFailsAndIsAskedAgain(addon, 'getdetails', 'trakt_show', url='100')

    def test_imdb_ratings_not_loaded(self):
        addon = Addon(self, {'ratings': 'IMDb'})
        addon.kodi.imdb['loaded'] = False
        self.assertFalse(addon.call('getdetails', url='100')['succeeded'])
        self.assertTrue(addon.kodi.logged('getdetails failed: IMDb ratings: no dataset loaded'))

    def test_episodes_english_text(self):
        addon = Addon(self, {'languageDetails': 'de-DE'})
        self.assertFailsAndIsAskedAgain(addon, 'getepisodelist', 'season_en', url=guide())

    def test_trakt_episode(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        self.assertFailsAndIsAskedAgain(addon, 'getepisodedetails', 'trakt_episode',
                                        url='100/1/3')

    def test_show_for_the_trakt_rating(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        self.assertFailsAndIsAskedAgain(addon, 'getepisodedetails', 'show', url='100/1/3')

    def test_nothing_of_a_failed_show_kept_on_disk(self):
        for kind in ('fanart', 'season_data'):
            with self.subTest(kind=kind):
                addon = Addon(self)
                addon.sites.failing[kind] = 1
                self.assertFalse(addon.call('getdetails', url='100')['succeeded'])
                self.assertIsNone(addon.scraper.art_cache.load('100'))

    def test_what_isnt_there_is_no_failure(self):
        self.assertTrue(self.addon.call('getdetails', url='101')['succeeded'])  # no fanart.tv art
        addon = Addon(self, {'ratings': 'Trakt'})
        self.assertTrue(addon.call('getdetails', url='101')['succeeded'])  # not on Trakt

    # ---------------------------------------------------------------- getartwork's unique ids

    def test_artwork_by_the_tmdb_id_among_the_unique_ids(self):
        # An nfo made the show's default id TVDB's
        art = self.addon.call('getartwork', id='500',
                              uniqueIDs=json.dumps({'tmdb': '100', 'tvdb': '500'}))
        self.assertTrue(art['succeeded'])
        self.assertEqual(self.asked.get('find', 0), 0)

    def test_artwork_by_another_sites_unique_id(self):
        art = self.addon.call('getartwork', id='500', uniqueIDs=json.dumps({'imdb': 'tt0000100'}))
        self.assertTrue(art['succeeded'])
        self.assertEqual(self.asked['find'], 1)

    def test_artwork_by_the_id_alone(self):
        self.assertTrue(self.addon.call('getartwork', id='100')['succeeded'])

    def test_artwork_not_by_another_sites_id_tmdb_hasnt(self):
        # TVDB's id 100 isn't TMDB's show 100
        art = self.addon.call('getartwork', id='100', uniqueIDs=json.dumps({'tvdb': '100'}))
        self.assertFalse(art['succeeded'])
        self.assertEqual(self.asked['find'], 1)
        self.assertEqual(self.asked.get('show', 0), 0)


if __name__ == '__main__':
    unittest.main()
