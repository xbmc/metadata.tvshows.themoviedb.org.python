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

    # ---------------------------------------------------------------- complete=1

    def test_episode_list_with_the_details(self):
        listed = self.addon.call('getepisodelist', url=guide(), complete='1')
        self.assertEqual(len(listed['items']), 17)
        item = listed['listitems'][4]  # 1x3
        self.assertEqual(item.properties.get('video.complete'), 'true')
        self.assertEqual(item.tag.calls.get('setPlot'), 'Overview 1.3')
        self.assertEqual(self.asked.get('episode', 0), 0)  # all from the guide

    def test_episode_list_without_the_details(self):
        listed = self.addon.call('getepisodelist', url=guide())
        self.assertFalse(any(i.properties.get('video.complete') for i in listed['listitems']))

    def test_episode_group_list_without_the_details(self):
        # its numbers aren't the episodes' own: Kodi asks for each one's details instead
        listed = self.addon.call('getepisodelist', url=guide(ep_group='g1'), complete='1')
        self.assertFalse(any(i.properties.get('video.complete') for i in listed['listitems']))

    def test_episode_list_with_the_details_and_trakt_ratings(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        listed = addon.call('getepisodelist', url=guide(), complete='1')
        item = listed['listitems'][4]
        self.assertEqual(item.tag.calls['setRating']['trakt'][0], 7.25)

    def test_an_episode_whose_details_fail_is_listed_without_them(self):
        self.failing.update(episode_extras=1, episode=1)
        listed = self.addon.call('getepisodelist', url=guide(), complete='1')
        self.assertTrue(listed['succeeded'])
        self.assertEqual(len(listed['items']), 17)
        self.assertIsNone(listed['listitems'][0].properties.get('video.complete'))
        self.assertEqual(listed['listitems'][1].properties.get('video.complete'), 'true')
        # what Kodi asks if the episode matches a file
        self.assertTrue(self.addon.call('getepisodedetails', url=listed['items'][0])['succeeded'])

    def test_an_episode_whose_rating_fails_is_listed_without_its_details(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        addon.sites.failing.update(trakt_season=3, trakt_episode=1)
        listed = addon.call('getepisodelist', url=guide(), complete='1')
        self.assertTrue(listed['succeeded'])
        marked = [i.properties.get('video.complete') for i in listed['listitems']]
        self.assertEqual(marked, [None] + ['true'] * 16)

    def test_episode_group_numbered_as_aired_without_the_details(self):
        listed = self.addon.call('getepisodelist', url=guide(ep_group='same'), complete='1')
        self.assertEqual(listed['items'], ['100/1/1'])
        self.assertIsNone(listed['listitems'][0].properties.get('video.complete'))

    # ---------------------------------------------------------------- seasons=

    def test_episode_list_of_the_seasons_asked_for(self):
        listed = self.addon.call('getepisodelist', url=guide(tmdb='300'), seasons='20,22')
        self.assertEqual(listed['items'], ['300/20/1', '300/22/1'])
        self.assertEqual(self.asked['all_seasons'], 1)

    def test_more_seasons_asked_for_later(self):
        self.addon.call('getepisodelist', url=guide(tmdb='300'), seasons='1')
        listed = self.addon.call('getepisodelist', url=guide(tmdb='300'), seasons='2')
        # only the season asked for, though season 1 is kept: Kodi could match an episode of it
        self.assertEqual(listed['items'], ['300/2/1'])
        self.assertEqual(self.asked['all_seasons'], 2)
        listed = self.addon.call('getepisodelist', url=guide(tmdb='300'))
        self.assertEqual(len(listed['items']), 22)
        asked = dict(self.asked)
        listed = self.addon.call('getepisodelist', url=guide(tmdb='300'), seasons='1,99')
        self.assertEqual(listed['items'], ['300/1/1'])
        self.assertEqual(self.asked, asked)  # all kept

    def test_trakt_ratings_of_seasons_asked_for_later(self):
        addon = Addon(self, {'ratings': 'Trakt'})
        for season in ('1', '2', '1'):
            listed = addon.call('getepisodelist', url=guide(tmdb='300'), complete='1',
                                seasons=season)
            self.assertEqual(listed['listitems'][0].tag.calls['setRating']['trakt'][0], 7.25)
        self.assertEqual(addon.sites.asked['trakt_season'], 2)  # each season's once
        self.assertEqual(addon.sites.asked.get('trakt_episode', 0), 0)

    def test_seasons_the_show_hasnt(self):
        listed = self.addon.call('getepisodelist', url=guide(), seasons='7')
        self.assertEqual(len(listed['items']), 17)  # all

    def test_seasons_of_an_episode_group(self):
        # its seasons aren't TMDB's: all of TMDB's are fetched
        listed = self.addon.call('getepisodelist', url=guide(ep_group='g1'), seasons='2')
        self.assertEqual(len(listed['items']), 12)  # the group's
        self.assertEqual(self.addon.cache['100']['seasons_fetched'], {0, 1, 2})

    def test_a_failed_season_keeps_nothing_of_it(self):
        self.failing['all_seasons'] = 1
        self.addon.call('getepisodelist', url=guide(tmdb='300'), seasons='3')
        self.assertNotIn('episodes', self.addon.cache.get('300', {}))
        self.assertEqual(self.addon.call('getepisodelist', url=guide(tmdb='300'),
                                         seasons='3')['items'], ['300/3/1'])


if __name__ == '__main__':
    unittest.main()
