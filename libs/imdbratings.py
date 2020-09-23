import re
import requests
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout, RequestException

IMDB_RATINGS_URL = 'https://www.imdb.com/title/{}/'

IMDB_RATING_REGEX = re.compile(r'itemprop="ratingValue".*?>.*?([\d.]+).*?<')
IMDB_VOTES_REGEX = re.compile(r'itemprop="ratingCount".*?>.*?([\d,]+).*?<')

# get the tv show info via imdb
def get_details(imdb_id):
    if not imdb_id:
        return {}
    votes, rating = _get_ratinginfo(imdb_id)
    return _assemble_imdb_result(votes, rating)

def _get_ratinginfo(imdb_id):
    try:
        response = requests.get(IMDB_RATINGS_URL.format(imdb_id))
    except (Timeout, RequestsConnectionError, RequestException) as ex:
        return _format_error_message(ex)
    return _parse_imdb_result(response.text if response and response.status_code == 200 else '')

def _assemble_imdb_result(votes, rating):
    result = {}
    if votes and rating:
        result['ratings'] = {'imdb': {'votes': votes, 'rating': rating}}
    return result

def _parse_imdb_result(input_html):
    rating = _parse_imdb_rating(input_html)
    votes = _parse_imdb_votes(input_html)
    return votes, rating

def _parse_imdb_rating(input_html):
    match = re.search(IMDB_RATING_REGEX, input_html)
    if (match):
        return float(match.group(1))
    return None

def _parse_imdb_votes(input_html):
    match = re.search(IMDB_VOTES_REGEX, input_html)
    if (match):
        return int(match.group(1).replace(',', ''))
    return None

def _format_error_message(ex):
    message = type(ex).__name__
    if hasattr(ex, 'message'):
        message += ": {0}".format(ex.message)
    return {'error': message}
