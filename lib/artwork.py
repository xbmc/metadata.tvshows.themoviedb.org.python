# SPDX-License-Identifier: GPL-3.0-or-later

"""Artwork classification, scoring, and byte-aware selection.

Images are classified by art type, ranked by language tier then
quality tier (voted+HD > voted > unvoted), and limited to byte
budgets (c06/c11) to enforce MySQL TEXT limit.
"""

from math import sqrt

_IMG_ORIGINAL = 'https://image.tmdb.org/t/p/original'
_IMG_W500 = 'https://image.tmdb.org/t/p/w500'
_IMG_W780 = 'https://image.tmdb.org/t/p/w780'

# MySQL TEXT = 65,535 bytes; 5K margin for safety
_C06_BUDGET = 60000
_C11_BUDGET = 60000
_C11_WRAPPER = 17  # <fanart></fanart>

_SPARSE_THRESHOLD = 3
_TEXT_BEARING = frozenset(('poster', 'landscape', 'clearlogo', 'banner', 'clearart'))
_HD_PIXELS = 1920 * 1080


def set_artwork(li, show_info, settings):
    """Main entry: classify, score, select, output to ListItem."""
    vtag = li.getVideoInfoTag()
    user_lang = settings['lang_images'][:2].lower()
    cat_kart = settings.get('cat_keyart', True)
    cat_land = settings.get('cat_landscape', True)

    candidates = []
    _classify_images(
        candidates, show_info.get('images', {}),
        None, cat_kart, cat_land,
    )
    for season in show_info.get('seasons', []):
        snum = season.get('season_number', 0)
        simages = season.get('images')
        if simages:
            _classify_images(
                candidates, simages,
                snum, cat_kart, cat_land,
            )

    prefer_maxres = settings.get('prefer_maxres', False)
    for c in candidates:
        if c['art_type'] == 'clearlogo':
            is_fanart = c.get('url', '').startswith('https://assets.fanart.tv/')
            pixels = min((c.get('width') or 0) * (c.get('height') or 0), 800 * 310)
            base = (is_fanart, pixels, c.get('vote_count') or 0)
        else:
            base = _score(c, prefer_maxres)
        if c['art_type'] in _TEXT_BEARING:
            lang_tier = 4 - _lang_sort_key(c.get('language'), user_lang)[0]
            c['score'] = (lang_tier,) + base
        else:
            c['score'] = base

    c06 = [c for c in candidates if c['column'] == 'c06']
    c11 = [c for c in candidates if c['column'] == 'c11']
    keep_c06 = _select(c06, _C06_BUDGET)
    keep_c11 = _select(c11, _C11_BUDGET - _C11_WRAPPER)

    fanart_urls = []
    for c in keep_c11:
        fanart_urls.append({'image': c['url']})
    if fanart_urls:
        try:
            vtag.setAvailableFanart(fanart_urls)
        except AttributeError:
            li.setAvailableFanart(fanart_urls)

    for c in keep_c06:
        kwargs = {'arttype': c['art_type'], 'preview': c['preview']}
        if c['season'] is not None:
            kwargs['season'] = c['season']
        vtag.addAvailableArtwork(c['url'], **kwargs)


def _classify_images(candidates, images, season, cat_kart, cat_land):
    """Classify images and append to candidates list."""
    for raw in images.get('posters', []):
        entry = _make_entry(raw, _IMG_W500)
        if not entry:
            continue
        lang = raw.get('iso_639_1')
        if (lang is None or lang == 'xx') and cat_kart:
            entry.update(art_type='keyart', column='c06', season=season)
        else:
            entry.update(art_type='poster', column='c06', season=season)
        candidates.append(entry)

    for raw in images.get('backdrops', []):
        entry = _make_entry(raw, _IMG_W780)
        if not entry:
            continue
        lang = raw.get('iso_639_1')
        if lang and lang != 'xx' and cat_land:
            entry.update(art_type='landscape', column='c06', season=season)
        else:
            entry.update(art_type='fanart', column='c11', season=season)
        candidates.append(entry)

    for raw in images.get('logos', []):
        entry = _make_entry(raw, _IMG_W500)
        if not entry:
            continue
        entry.update(art_type='clearlogo', column='c06', season=season)
        candidates.append(entry)

    for art_type in ('banner', 'clearart', 'characterart'):
        for raw in images.get(art_type, []):
            entry = _make_entry(raw, _IMG_W500)
            if not entry:
                continue
            entry.update(art_type=art_type, column='c06', season=season)
            candidates.append(entry)

    for raw in images.get('landscape', []):
        entry = _make_entry(raw, _IMG_W780)
        if not entry:
            continue
        entry.update(art_type='landscape', column='c06', season=season)
        candidates.append(entry)


def _type_cap(available):
    """Limit how many of one type get priority. Grows slowly with count."""
    if available <= _SPARSE_THRESHOLD:
        return available
    return _SPARSE_THRESHOLD + int(sqrt(available))


def _select(entries, byte_budget):
    """Pick art fairly across types, then fill the rest by quality.

    Each type gets a small share (priority pool). Whatever budget
    remains is filled with the best-scoring leftovers, usually posters.

    """
    if not entries:
        return []

    by_type = {}
    for e in entries:
        by_type.setdefault(e['art_type'], []).append(e)

    priority = []
    overflow = []
    for type_entries in by_type.values():
        type_entries.sort(key=lambda e: e['score'], reverse=True)
        cap = _type_cap(len(type_entries))
        priority.extend(type_entries[:cap])
        overflow.extend(type_entries[cap:])

    priority.sort(key=lambda e: e['score'], reverse=True)
    selected = []
    used = 0
    for e in priority:
        cost = _byte_cost(e)
        if used + cost <= byte_budget:
            selected.append(e)
            used += cost

    overflow.sort(key=lambda e: e['score'], reverse=True)
    for e in overflow:
        cost = _byte_cost(e)
        if used + cost <= byte_budget:
            selected.append(e)
            used += cost

    return selected


def _byte_cost(entry):
    """XML serialization cost for one image entry."""
    if entry['column'] == 'c11':
        # <thumb colors="" preview="">URL</thumb>\n
        # setAvailableFanart only receives {'image': url}, Kodi stores preview=""
        return 36 + len(entry['url'])
    # <thumb spoof="" cache="" [season="N" type="season" ]aspect="TYPE" preview="PREVIEW">URL</thumb>
    cost = 54 + len(entry['art_type']) + len(entry['preview']) + len(entry['url'])
    if entry['season'] is not None:
        cost += 24 + len(str(entry['season']))
    return cost


def _score(entry, prefer_maxres=False):
    """Comparable tuple: (quality_tier, primary, secondary, tiebreaker).

    Tiers: voted+HD(3) > voted(2) > unvoted+HD(1) > unvoted(0).
    Tier 3 sorts by vote_average unless prefer_maxres, rest by pixels.
    """
    w = entry.get('width') or 0
    h = entry.get('height') or 0
    pixels = w * h
    va = entry.get('vote_average') or 0
    vc = entry.get('vote_count') or 0

    voted = vc > 0
    hd = pixels >= _HD_PIXELS

    if voted and hd:
        tier = 3
    elif voted:
        tier = 2
    elif hd:
        tier = 1
    else:
        tier = 0

    if tier == 3 and not prefer_maxres:
        return (tier, va, pixels, vc)
    return (tier, pixels, va, vc)


def _make_entry(raw_image, preview_base):
    """Convert a raw image dict into a candidate entry."""
    path = raw_image.get('file_path')
    if not path or path.endswith('.svg'):
        return None
    if raw_image.get('type') == 'fanarttv':
        url = path
        preview = path.replace('/fanart/', '/preview/', 1)
    else:
        url = '{}{}'.format(_IMG_ORIGINAL, path)
        preview = '{}{}'.format(preview_base, path)
    return {
        'url': url,
        'preview': preview,
        'language': raw_image.get('iso_639_1'),
        'vote_average': raw_image.get('vote_average') or 0,
        'vote_count': raw_image.get('vote_count') or 0,
        'width': raw_image.get('width') or 0,
        'height': raw_image.get('height') or 0,
    }


def _lang_sort_key(lang, user_lang):
    if lang:
        lang = lang.lower()
    if lang == user_lang:
        return (0,)
    if lang == 'en' and user_lang != 'en':
        return (1,)
    if not lang or lang == 'xx':
        return (2,)
    return (3, lang or '')
