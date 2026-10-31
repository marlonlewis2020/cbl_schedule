import json
from contextlib import closing
import tempfile
import threading
import unittest
from urllib import request, error
from server import AppServer

class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = AppServer(0, self.temp.name, upstream=lambda *args: [])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.model = {'roster': [], 'pools': [], 'results': [], 'controls': {'week': '2026-11-02', 'weeks': 3}, 'user': {'firstName': 'Test'}}
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()
    def call(self, path='/api/workspace', method='GET', data=None, auth=True, extra=None):
        headers = {'Content-Type': 'application/json'}
        if auth: headers['X-CBL-Connector-Token'] = self.server.token
        headers.update(extra or {})
        req = request.Request(self.url+path, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=5) as response: return response.status, response.read()
        except error.HTTPError as exc: return exc.code, exc.read()
    def test_workspace_save_reload_conflict_and_validation(self):
        self.assertEqual(json.loads(self.call()[1]), {'model':None,'version':0})
        self.assertEqual(self.call(method='PUT',data={'model':self.model,'version':0})[0],200)
        self.assertEqual(json.loads(self.call()[1])['model'],self.model)
        self.assertEqual(self.call(method='PUT',data={'model':self.model,'version':0})[0],409)
        self.assertEqual(self.call(method='PUT',data={'model':{},'version':1})[0],400)
        self.model['apiKey']='dummy'
        self.assertEqual(self.call(method='PUT',data={'model':self.model,'version':1})[0],400)
        # Reopening a second server against the same disk preserves workspace.
        second=AppServer(0,self.temp.name)
        try:
            import sqlite3
            with closing(sqlite3.connect(second.database)) as db:
                self.assertEqual(db.execute('select version from workspace').fetchone()[0],1)
        finally: second.server_close()
    def test_session_host_origin_and_app(self):
        self.assertEqual(self.call(auth=False)[0],403)
        self.assertEqual(self.call(extra={'Origin':'https://untrusted.example'})[0],403)
        self.assertEqual(self.call(extra={'Host':'untrusted.example'})[0],403)
        if self.server.split_app:
            self.assertEqual(self.call('/CBL-Scheduler2.js',extra={'Origin':'https://untrusted.example'})[0],403)
        code,html=self.call('/')
        self.assertEqual(code,200)
        if self.server.split_app:
            self.assertIn(b'<script src="server-storage-v2.js"></script>',html)
            self.assertIn(b'sourcePickerDialog',html)
            self.assertEqual(self.call('/CBL-Scheduler2.js')[0],200)
            self.assertIn(b'data-control="weeks"',self.call('/CBL-Scheduler2.js')[1])
            self.assertEqual(self.call('/CBL-Scheduler2.config.js')[0],200)
            self.assertEqual(self.call('/CBL-MicrosoftAuth.html')[0],200)
        else:
            self.assertIn(b'const browserRecordStore=store;',html)
            self.assertIn(b'Workforce Links',html)
            self.assertIn(b'data-control="weeks"',html)
        self.assertEqual(self.call('/bamboo/time-offs?start=2026-11-02&end=2026-11-08',extra={'Authorization':'Basic ZHVtbXk6eA=='})[0],200)
        self.assertEqual(self.call('/../server.py')[0],404)
if __name__=='__main__': unittest.main()
