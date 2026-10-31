#!/usr/bin/env python3
"""Local Python web host with transactional SQLite workspace persistence."""
import argparse
from contextlib import closing
import hmac
import json
from pathlib import Path
import sqlite3
import threading
import webbrowser
from urllib.parse import urlsplit
from bamboo_connector import ConnectorServer, ConnectorHandler

ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT.parents[1]
SPLIT_APP_PATH = APP_ROOT / 'CBL-Scheduler2.html'
MAX_BYTES = 64 * 1024 * 1024

class AppServer(ConnectorServer):
    def __init__(self, port=8765, data_dir=None, upstream=None):
        self.data_dir = Path(data_dir or ROOT / 'data').resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.data_dir / 'workspace.sqlite3'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, content TEXT NOT NULL)')
        self.database.chmod(0o600)
        self.split_app = SPLIT_APP_PATH.is_file()
        app_path = SPLIT_APP_PATH if self.split_app else ROOT / 'CBL-Scheduling-Command-Centre.html'
        super().__init__(port, app_path, upstream=upstream)
        self.RequestHandlerClass = AppHandler

class AppHandler(ConnectorHandler):
    server_version = 'CBLScheduler/1.0'
    def authorized(self):
        return self.allowed_request() and hmac.compare_digest(self.headers.get('X-CBL-Connector-Token', ''), self.server.token)
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/workspace':
            if not self.authorized():
                return self.send_data(403, {'error': 'Session expired. Reopen the full URL printed by the launcher.'})
            with closing(sqlite3.connect(self.server.database)) as db:
                row = db.execute('SELECT version,content FROM workspace WHERE id=1').fetchone()
            return self.send_data(200, {'version': row[0] if row else 0, 'model': json.loads(row[1]) if row else None})
        if self.server.split_app and path in {
            '/CBL-Scheduler2.css',
            '/CBL-Scheduler2.js',
            '/CBL-Scheduler2.config.js',
            '/CBL-MicrosoftAuth.html',
            '/server-storage-v2.js',
        }:
            if not self.allowed_request():
                return self.send_data(403, {'error': 'Host or origin is not allowed.'})
            asset = {
                '/CBL-Scheduler2.css': APP_ROOT / 'CBL-Scheduler2.css',
                '/CBL-Scheduler2.js': APP_ROOT / 'CBL-Scheduler2.js',
                '/CBL-Scheduler2.config.js': APP_ROOT / 'CBL-Scheduler2.config.js',
                '/CBL-MicrosoftAuth.html': APP_ROOT / 'CBL-MicrosoftAuth.html',
                '/server-storage-v2.js': ROOT / 'server-storage-v2.js',
            }[path]
            try:
                content_type = 'text/css; charset=utf-8' if asset.suffix == '.css' else 'text/html; charset=utf-8' if asset.suffix == '.html' else 'text/javascript; charset=utf-8'
                return self.send_data(200, asset.read_bytes(), content_type)
            except OSError:
                return self.send_data(404, {'error': 'Required scheduler asset is missing.'})
        if path in {'/', '/CBL-Scheduling-Command-Centre.html', '/CBL-Scheduler2.html'}:
            if not self.allowed_request():
                return self.send_data(403, {'error': 'Host or origin is not allowed.'})
            html = self.server.app_path.read_text(encoding='utf-8')
            if self.server.split_app:
                marker = '<script src="CBL-Scheduler2.js"></script>'
                if marker not in html:
                    return self.send_data(500, {'error': 'Scheduler page is missing its application script.'})
                html = html.replace(marker, '<script src="server-storage-v2.js"></script>' + marker)
            else:
                bridge = (ROOT / 'server-storage.js').read_text(encoding='utf-8')
                html = html.replace('if(!globalThis.TEST_MODE)init();', bridge + '\nif(!globalThis.TEST_MODE)init();')
                html = html.replace('The source inputs, settings, lock state and weekly schedule snapshots are saved in this browser using IndexedDB. Download a workspace backup or portable HTML for a durable copy. Browser storage is not shared with other team members and may be cleared by browser policies.', 'The source inputs, settings, lock state and weekly schedules are saved in the Python app’s SQLite database on this computer. Keep the data folder between launches. Use a workspace backup or portable HTML for an additional copy. Browser tabs use a version check to prevent silently overwriting newer saved changes.')
                html = html.replace('Browser saving where available; use workspace backup or portable HTML to retain session-only work.', 'Python web app · SQLite workspace saving on this computer. Keep backups of the data folder.')
            return self.send_data(200, html.encode('utf-8'), 'text/html; charset=utf-8')
        return super().do_GET()
    def do_PUT(self):
        if urlsplit(self.path).path != '/api/workspace':
            return self.send_data(404, {'error': 'Unknown endpoint.'})
        if not self.authorized():
            return self.send_data(403, {'error': 'Invalid session, host or origin.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BYTES:
                return self.send_data(413, {'error': 'Workspace must be smaller than 64 MB.'})
            if self.headers.get_content_type() != 'application/json':
                return self.send_data(415, {'error': 'JSON required.'})
            body = json.loads(self.rfile.read(length))
            model, version = body['model'], body['version']
            if not isinstance(model, dict) or not isinstance(version, int) or isinstance(version, bool):
                raise ValueError()
            if not all(isinstance(model.get(k), list) for k in ['roster', 'pools', 'results']) or not isinstance(model.get('controls'), dict):
                raise ValueError()
            # API secrets must never be stored in the workspace payload.
            def secrets_present(value):
                if isinstance(value, dict):
                    return any(k.lower() in {'apikey','apipassword','bamboocredentials','authorization'} or secrets_present(v) for k,v in value.items())
                return isinstance(value, list) and any(secrets_present(v) for v in value)
            if secrets_present(model):
                return self.send_data(400, {'error': 'Remove API credentials from the workspace.'})
            content = json.dumps(model, ensure_ascii=False)
            with closing(sqlite3.connect(self.server.database, timeout=10)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT version FROM workspace WHERE id=1').fetchone()
                current = row[0] if row else 0
                if current != version:
                    return self.send_data(409, {'error': 'Another tab saved changes. Export a backup of this tab, then reload before editing.'})
                db.execute('INSERT OR REPLACE INTO workspace VALUES(1,?,?)', (current+1, content))
            return self.send_data(200, {'version': current+1})
        except (ValueError, KeyError, TypeError, UnicodeError):
            return self.send_data(400, {'error': 'Invalid workspace JSON.'})
        except sqlite3.Error:
            return self.send_data(500, {'error': 'Workspace save failed. Check disk space and data folder permissions.'})

def main():
    parser = argparse.ArgumentParser(description='CBL Workforce Scheduler Python web app — local computer only')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        server = AppServer(args.port, args.data_dir)
    except OSError as exc:
        raise SystemExit(f'Could not start: {exc}. Try --port 8766.') from exc
    path = 'CBL-Scheduler2.html' if server.split_app else 'CBL-Scheduling-Command-Centre.html'
    url = f'http://localhost:{server.server_address[1]}/{path}#connector={server.token}'
    print('CBL Workforce Scheduler · Python web app')
    print('Workspace database:', server.database)
    print('Open this session URL:\n' + url)
    print('Keep this window open. Press Ctrl+C to stop.')
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
