"""get_json() against a local HTTP server: the retry, the timeout, and a 404 told from a failure."""
import gzip
import socket
import threading
import time
import unittest
import unittest.mock as mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from test.unittests.kodi_stubs import Addon

PLANS = {}  # path -> the answers, one a request, the last repeated
HITS = {}  # path -> requests


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split('?')[0]
        HITS[path] = HITS.get(path, 0) + 1
        steps = PLANS[path]
        step = steps.pop(0) if len(steps) > 1 else steps[0]
        kind = step[0]
        if kind in ('json', 'gzip-no-header'):
            body = step[1].encode()
            if kind == 'gzip-no-header':
                body = gzip.compress(body)  # as a CDN has sent, without Content-Encoding
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif kind == 'status':
            body = b'{"status_code": 34}'
            self.send_response(step[1])
            for key, value in step[2].items():
                self.send_header(key, value)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif kind == 'reset':
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                       b'\x01\x00\x00\x00\x00\x00\x00\x00')
            self.connection.close()
        elif kind == 'short':
            self.send_response(200)
            self.send_header('Content-Length', '1000')
            self.end_headers()
            self.wfile.write(b'{"a": 1')
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
            self.close_connection = True
        elif kind == 'stall':
            time.sleep(step[1])
            try:
                self.send_response(200)
                self.end_headers()
            except OSError:
                pass


def setUpModule():
    global SERVER, BASE
    SERVER = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    SERVER.daemon_threads = True
    threading.Thread(target=SERVER.serve_forever, daemon=True).start()
    BASE = 'http://127.0.0.1:{}'.format(SERVER.server_address[1])


def tearDownModule():
    SERVER.shutdown()
    SERVER.server_close()


class TestGetJson(unittest.TestCase):
    def setUp(self):
        self.addon = Addon(self, fake_sites=False)
        self.request = self.addon.request
        patch = mock.patch.object(self.request, '_TIMEOUT', 0.5)
        patch.start()
        self.addCleanup(patch.stop)

    def get(self, path, *plan):
        PLANS[path] = list(plan)
        HITS[path] = 0
        return self.request.get_json(BASE + path + '?api_key=SECRET&q=x',
                                     {'Accept': 'application/json'}, 'TEST GET ' + path)

    def assertFails(self, path, *plan):
        with self.assertRaises(self.request.RequestFailed) as failure:
            self.get(path, *plan)
        self.assertIn('TEST GET ' + path + ' failed', str(failure.exception))
        self.assertTrue(self.addon.kodi.logged('TEST GET {} failed:'.format(path)))

    def test_answer(self):
        self.assertEqual(self.get('/a', ('json', '{"x": 1}')), {'x': 1})
        self.assertEqual(HITS['/a'], 1)

    def test_5xx_retried(self):
        self.assertEqual(self.get('/b', ('status', 503, {}), ('json', '{"x": 2}')), {'x': 2})
        self.assertEqual(HITS['/b'], 2)
        self.assertEqual(self.addon.kodi.waits, [1])

    def test_429_waits_as_asked(self):
        self.assertEqual(self.get('/c', ('status', 429, {'Retry-After': '3'}),
                                  ('json', '{"x": 3}')), {'x': 3})
        self.assertEqual(HITS['/c'], 2)
        self.assertEqual(self.addon.kodi.waits, [3])

    def test_429_waits_ten_seconds_at_most(self):
        self.get('/c2', ('status', 429, {'Retry-After': '3600'}), ('json', '{}'))
        self.assertEqual(self.addon.kodi.waits, [10])

    def test_404_is_not_found(self):
        self.assertIsNone(self.get('/d', ('status', 404, {})))
        self.assertEqual(HITS['/d'], 1)
        self.assertTrue(self.addon.kodi.logged('TEST GET /d: not found'))

    def test_reset_retried(self):
        self.assertEqual(self.get('/e', ('reset',), ('json', '{"x": 5}')), {'x': 5})
        self.assertEqual(HITS['/e'], 2)

    def test_body_cut_short_retried(self):
        self.assertEqual(self.get('/f', ('short',), ('json', '{"x": 6}')), {'x': 6})
        self.assertEqual(HITS['/f'], 2)

    def test_not_json_twice(self):
        self.assertFails('/g', ('json', '<html>a proxy\'s page</html>'))
        self.assertEqual(HITS['/g'], 2)

    def test_stall_twice(self):
        self.assertFails('/h', ('stall', 1.5))
        self.assertEqual(HITS['/h'], 2)

    def test_5xx_twice(self):
        self.assertFails('/i', ('status', 500, {}))
        self.assertEqual(HITS['/i'], 2)

    def test_4xx_not_retried(self):
        self.assertFails('/j', ('status', 401, {}))
        self.assertEqual(HITS['/j'], 1)

    def test_reset_twice(self):
        self.assertFails('/k', ('reset',))
        self.assertEqual(HITS['/k'], 2)

    def test_gzip_body_without_its_header(self):
        self.assertEqual(self.get('/l', ('gzip-no-header', '{"x": 12}')), {'x': 12})

    def test_kodi_stopping_is_not_retried(self):
        self.addon.kodi.abort = True
        self.assertFails('/m', ('status', 503, {}))
        self.assertEqual(HITS['/m'], 1)

    def test_api_key_not_logged(self):
        self.get('/n', ('status', 503, {}), ('json', '{}'))
        with self.assertRaises(self.request.RequestFailed):
            self.get('/o', ('status', 500, {}))
        self.assertTrue(self.addon.kodi.logs)
        self.assertFalse(self.addon.kodi.logged('SECRET'))


if __name__ == '__main__':
    unittest.main()
