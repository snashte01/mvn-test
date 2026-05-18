#!/usr/bin/env python3
"""SAP Landscape Manager - main HTTP server (stdlib only, no pip required)."""

from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse
import traceback
import datetime
import os
import sys

PORT = int(os.environ.get('SAP_MGMT_PORT', 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class SAPMgmtHandler(BaseHTTPRequestHandler):

    def _send_html(self, content, status=200):
        try:
            body = content.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client disconnected before we could respond

    def _redirect(self, location):
        try:
            self.send_response(302)
            self.send_header('Location', location)
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_post_params(self):
        length = int(self.headers.get('Content-Length', 0))
        if not length:
            return {}
        raw = self.rfile.read(length).decode('utf-8')
        return urllib.parse.parse_qs(raw, keep_blank_values=True)

    def _error_page(self, message):
        from templates.base import render
        content = f'<div class="alert alert-danger"><pre>{message}</pre></div>'
        return render('Error', content)

    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/') or '/'
        qs   = urllib.parse.parse_qs(self.path.split('?', 1)[-1] if '?' in self.path else '')
        try:
            if path in ('/', '/dashboard'):
                from templates.dashboard import render_dashboard
                self._send_html(render_dashboard())
            elif path == '/fs':
                from templates.filesystem import render_fs_page
                self._send_html(render_fs_page())
            elif path == '/fs/status':
                job_id = qs.get('job', [''])[0]
                from handlers.jobs import get
                from templates.filesystem import render_waiting_page
                job = get(job_id)
                if not job:
                    self._send_html(self._error_page(f'Job {job_id!r} not found.'), 404)
                elif job['status'] == 'running':
                    self._send_html(render_waiting_page(job_id, job['ts']))
                else:
                    self._send_html(job['result'])
            elif path == '/hsr':
                from templates.hsr import render_hsr_page
                self._send_html(render_hsr_page())
            elif path == '/backup':
                from templates.backup import render_backup_page
                self._send_html(render_backup_page())
            elif path == '/backup/catalog/status':
                job_id = qs.get('job', [''])[0]
                from handlers.jobs import get
                job = get(job_id)
                if not job:
                    self._send_html(self._error_page(f'Job {job_id!r} not found.'), 404)
                elif job['status'] == 'running':
                    elapsed = int(datetime.datetime.now().timestamp() - job['ts'])
                    from templates.base import render
                    waiting = (
                        '<meta http-equiv="refresh" content="5;url=/backup/catalog/status?job=' + job_id + '">'
                        '<div class="card" style="text-align:center;padding:40px;">'
                        '<div style="font-size:2em;margin-bottom:12px;">&#9696;</div>'
                        '<strong>Querying HANA backup catalog via hdbsql...</strong>'
                        '<p style="color:#666;font-size:.9em;">Elapsed: ' + str(elapsed) + 's &nbsp;|&nbsp; Refreshes every 5 seconds.</p>'
                        '<p style="color:#aaa;font-size:.82em;">Job ID: <code>' + job_id + '</code></p>'
                        '</div>'
                    )
                    self._send_html(render('Backup Catalog – Querying', waiting, active_nav='backup'))
                else:
                    self._send_html(job['result'])
            elif path == '/backup/trigger/status':
                job_id = qs.get('job', [''])[0]
                from handlers.jobs import get
                job = get(job_id)
                if not job:
                    self._send_html(self._error_page(f'Job {job_id!r} not found.'), 404)
                elif job['status'] == 'running':
                    elapsed = int(datetime.datetime.now().timestamp() - job['ts'])
                    from templates.base import render
                    waiting = (
                        '<meta http-equiv="refresh" content="5;url=/backup/trigger/status?job=' + job_id + '">'
                        '<div class="card" style="text-align:center;padding:40px;">'
                        '<div style="font-size:2em;margin-bottom:12px;">&#9696;</div>'
                        '<strong>HANA backup running — waiting for completion...</strong>'
                        '<p style="color:#666;font-size:.9em;">Elapsed: ' + str(elapsed) + 's &nbsp;|&nbsp; Refreshes every 5 seconds.</p>'
                        '<p style="color:#aaa;font-size:.82em;">This may take 15–60 minutes for large databases.</p>'
                        '</div>'
                    )
                    self._send_html(render('Backup – Running', waiting, active_nav='backup'))
                else:
                    self._send_html(job['result'])
            elif path == '/health':
                from templates.healthcheck import render_health_page
                self._send_html(render_health_page())
            elif path == '/health/status':
                job_id = qs.get('job', [''])[0]
                from handlers.jobs import get
                job = get(job_id)
                if not job:
                    self._send_html(self._error_page(f'Job {job_id!r} not found.'), 404)
                elif job['status'] == 'running':
                    elapsed = int(datetime.datetime.now().timestamp() - job['ts'])
                    from templates.base import render
                    waiting = (
                        '<meta http-equiv="refresh" content="4;url=/health/status?job=' + job_id + '">'
                        '<div class="card" style="text-align:center;padding:40px;">'
                        '<div style="font-size:2em;margin-bottom:12px;">&#9696;</div>'
                        '<strong>Running health check across all SAP hosts via Ansible...</strong>'
                        '<p style="color:#666;font-size:.9em;">Elapsed: ' + str(elapsed) + 's &nbsp;|&nbsp; Page refreshes every 4 seconds.</p>'
                        '<p style="color:#aaa;font-size:.82em;">Job ID: <code>' + job_id + '</code></p>'
                        '</div>'
                    )
                    self._send_html(render('Health Check - Running', waiting, active_nav='health'))
                else:
                    self._send_html(job['result'])
            else:
                self._send_html(self._error_page('Page not found'), 404)
        except Exception:
            self._send_html(self._error_page(traceback.format_exc()), 500)

    def do_POST(self):
        params = self._read_post_params()
        path = self.path
        try:
            if path == '/fs/check':
                from handlers.filesystem import start_check
                job_id = start_check(params)
                self._redirect(f'/fs/status?job={job_id}')
            elif path == '/fs/extend':
                from handlers.filesystem import run_extend
                self._send_html(run_extend(params))
            elif path == '/hsr/check':
                from handlers.hsr import run_check
                self._send_html(run_check(params))
            elif path == '/backup/catalog':
                from handlers.backup import start_catalog
                job_id = start_catalog(params)
                self._redirect(f'/backup/catalog/status?job={job_id}')
            elif path == '/backup/trigger':
                from handlers.backup import start_trigger
                job_id = start_trigger(params)
                self._redirect(f'/backup/trigger/status?job={job_id}')
            elif path == '/health/check':
                from handlers.healthcheck import start_check
                job_id = start_check(params)
                self._redirect(f'/health/status?job={job_id}')
            else:
                self._send_html(self._error_page('Endpoint not found'), 404)
        except Exception:
            self._send_html(self._error_page(traceback.format_exc()), 500)

    def log_message(self, fmt, *args):
        sys.stdout.write(
            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{self.address_string()} {fmt % args}\n"
        )
        sys.stdout.flush()


class ThreadedHTTPServer(HTTPServer):
    """Handle each request in a dedicated daemon thread."""

    def server_bind(self):
        # Skip socket.getfqdn() — it does a reverse DNS lookup on 0.0.0.0
        # which hangs on RHEL hosts with slow or missing DNS.
        import socketserver
        socketserver.TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]

    def process_request(self, request, client_address):
        t = threading.Thread(
            target=self.finish_request,
            args=(request, client_address),
            daemon=True,
        )
        t.start()


if __name__ == '__main__':
    sys.path.insert(0, BASE_DIR)

    from db.audit import init_db
    init_db()

    os.makedirs('/tmp/sap_mgmt', exist_ok=True)

    server = ThreadedHTTPServer(('0.0.0.0', PORT), SAPMgmtHandler)
    print(f'SAP Landscape Manager running on http://0.0.0.0:{PORT}')
    print('Press Ctrl+C to stop.\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()
