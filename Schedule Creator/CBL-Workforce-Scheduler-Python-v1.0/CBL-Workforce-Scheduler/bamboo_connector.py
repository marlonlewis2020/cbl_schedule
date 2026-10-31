#!/usr/bin/env python3
"""CBL loopback-only BambooHR connector. Python 3.9+, standard library only."""
import argparse
import datetime as dt
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
from urllib import error, parse, request
import webbrowser

APP_FILE = 'CBL-Scheduling-Command-Centre.html'
BAMBOO_URL = 'https://cbljm.bamboohr.com/api/v1/time_off/whos_out'

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class ConnectorServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port, app_path, token=None, upstream=None):
        self.token = token or secrets.token_urlsafe(32)
        self.app_path = Path(app_path)
        self.upstream = upstream or self.fetch_bamboo
        super().__init__(('127.0.0.1', port), ConnectorHandler)
    def fetch_bamboo(self, start, end, authorization):
        url = BAMBOO_URL + '?' + parse.urlencode({'start': start, 'end': end})
        req = request.Request(url, headers={'Accept': 'application/json', 'Authorization': authorization}, method='GET')
        opener = request.build_opener(NoRedirect())
        with opener.open(req, timeout=20) as response:
            data = json.loads(response.read(10_000_001))
        if not isinstance(data, list):
            raise ValueError('BambooHR did not return a list of time-off records.')
        return data

class ConnectorHandler(BaseHTTPRequestHandler):
    server_version = 'CBLConnector/1.0'
    def log_message(self, fmt, *args):
        pass  # Never log authorization, personal records or request URLs.
    def allowed_request(self):
        port = self.server.server_address[1]
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        origin = self.headers.get('Origin')
        return self.headers.get('Host') in hosts and (not origin or origin in {f'http://{host}' for host in hosts})
    def send_data(self, status, payload, content_type='application/json; charset=utf-8'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        if self.allowed_request() and self.headers.get('Origin'):
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
    def do_OPTIONS(self):
        if not self.allowed_request() or parse.urlsplit(self.path).path not in {'/bamboo/time-offs', '/health'}:
            return self.send_data(403, {'error': 'Connector origin or endpoint is not allowed.'})
        self.send_response(204)
        if self.headers.get('Origin'):
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Accept, Authorization, X-CBL-Connector-Token')
        self.send_header('Access-Control-Max-Age', '300')
        self.end_headers()
    def do_GET(self):
        if not self.allowed_request():
            return self.send_data(403, {'error': 'Connector origin or host is not allowed.'})
        parsed = parse.urlsplit(self.path)
        if parsed.path in {'/', '/' + APP_FILE}:
            try:
                return self.send_data(200, self.server.app_path.read_bytes(), 'text/html; charset=utf-8')
            except OSError:
                return self.send_data(404, {'error': 'Place the Scheduling HTML in the connector folder.'})
        if parsed.path not in {'/health', '/bamboo/time-offs'}:
            return self.send_data(404, {'error': 'Unknown connector endpoint.'})
        token = self.headers.get('X-CBL-Connector-Token', '')
        if not token or not hmac.compare_digest(token, self.server.token):
            return self.send_data(403, {'error': 'Connector session expired. Reopen the URL printed by the connector.'})
        if parsed.path == '/health':
            return self.send_data(200, {'service': 'cbl-bamboo-local', 'ready': True})
        authorization = self.headers.get('Authorization', '')
        if not authorization.startswith('Basic ') or len(authorization) > 8192:
            return self.send_data(400, {'error': 'BambooHR Basic authorization is required.'})
        try:
            query = parse.parse_qs(parsed.query, keep_blank_values=True)
            if set(query) != {'start', 'end'} or any(len(v) != 1 for v in query.values()):
                raise ValueError('Provide one start and one end date.')
            start, end = query['start'][0], query['end'][0]
            a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
            if a.isoformat() != start or b.isoformat() != end or b < a or (b - a).days > 3660:
                raise ValueError('Invalid date range.')
        except (ValueError, KeyError):
            return self.send_data(400, {'error': 'Use valid start/end dates in YYYY-MM-DD format.'})
        try:
            data = self.server.upstream(start, end, authorization)
            return self.send_data(200, data)
        except error.HTTPError as exc:
            status = exc.code if exc.code in {400, 401, 403, 404, 422, 429, 500, 502, 503} else 502
            return self.send_data(status, {'error': f'BambooHR returned HTTP {exc.code}.', 'upstreamStatus': exc.code})
        except (error.URLError, TimeoutError, OSError):
            return self.send_data(502, {'error': 'The local connector could not reach BambooHR. Check this computer’s internet, VPN, proxy or certificate configuration.'})
        except (ValueError, json.JSONDecodeError):
            return self.send_data(502, {'error': 'BambooHR returned an invalid JSON time-off response.'})


def main():
    parser = argparse.ArgumentParser(description='Run the local CBL Scheduling app and BambooHR connector.')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    app = Path(__file__).resolve().parent / APP_FILE
    if not app.is_file():
        raise SystemExit(f'Keep {APP_FILE} in the same folder as connector.py.')
    try:
        server = ConnectorServer(args.port, app)
    except OSError as exc:
        raise SystemExit('Cannot start the local connector. Close an existing connector, or run python connector.py --port 8766.') from exc
    url = f'http://127.0.0.1:{server.server_address[1]}/#connector={server.token}'
    print('CBL Scheduling local connector is running on this computer only.')
    print('Leave this window open while using BambooHR. Press Ctrl+C to stop.')
    print('Open this session in your browser:\n' + url)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
