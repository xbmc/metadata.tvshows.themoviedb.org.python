from trakt import Trakt
from trakt.objects import Show

# get the show/episode info via imdb
def get_ratinginfo(imdb_id, season=None, episode=None):
    __client_id = "90901c6be3b2de5a4fa0edf9ab5c75e9a5a0fef2b4ee7373d8b63dcf61f95697"
    __client_secret = "c7e92c555f175794a16f18e51cfc3387aa4b7e9261e19c9c4f8fb567e3e36607"
    # Configure
    Trakt.configuration.defaults.client(
        id=__client_id,
        secret=__client_secret
    )

    with Trakt.configuration.http(retry=True):
        result = {}
        if season is None and episode is None:
            the_info = Trakt['shows'].get(imdb_id, extended='full').to_dict()
        else:
            the_info = Trakt['shows'].episode(imdb_id, season, episode, extended='full').to_dict()
        if (the_info):
            if 'votes' in the_info and 'rating' in the_info:
                result['ratings'] = {'trakt': {'votes': int(the_info['votes']), 'rating': float(the_info['rating'])}}
            elif 'rating' in the_info:
                result['ratings'] = {'trakt': {'rating': float(the_info['rating'])}}
        return result
