#!/bin/bash
# SAP Landscape Manager - Bootstrap script
# Creates the full project structure on the target RHEL host.
# Usage:
#   chmod +x bootstrap.sh
#   ./bootstrap.sh [install-dir]   (default: /opt/sap-landscape-mgmt)

set -euo pipefail

INSTALL_DIR="${1:-/opt/sap-landscape-mgmt}"

echo "======================================================"
echo " SAP Landscape Manager - Bootstrap"
echo " Target directory: ${INSTALL_DIR}"
echo "======================================================"

# ── Prerequisites check ────────────────────────────────────
echo ""
echo "[1/4] Checking prerequisites..."

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "  MISSING: $1 — install it first: dnf install $2 -y"
        MISSING=1
    else
        echo "  OK: $1 ($(command -v "$1"))"
    fi
}

MISSING=0
check_cmd python3   "python3"
check_cmd ansible-playbook "ansible-core"
check_cmd ssh       "openssh-clients"

if [[ $MISSING -eq 1 ]]; then
    echo ""
    echo "ERROR: Missing prerequisites above. Install them and re-run."
    exit 1
fi

# ── Directory structure ────────────────────────────────────
echo ""
echo "[2/4] Creating directory structure under ${INSTALL_DIR}..."

mkdir -p "${INSTALL_DIR}"/{handlers,templates,db,ansible/{playbooks,inventory},systemd}
touch "${INSTALL_DIR}"/handlers/__init__.py
touch "${INSTALL_DIR}"/templates/__init__.py
touch "${INSTALL_DIR}"/db/__init__.py
echo "  Done."

# ── Write files ────────────────────────────────────────────
echo ""
echo "[3/4] Writing project files..."

# ── server.py ──────────────────────────────────────────────
cat > "${INSTALL_DIR}/server.py" << 'PYEOF'
#!/usr/bin/env python3
"""SAP Landscape Manager - main HTTP server (stdlib only)."""

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
        body = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        try:
            if path in ('/', '/dashboard'):
                from templates.dashboard import render_dashboard
                self._send_html(render_dashboard())
            elif path == '/fs':
                from templates.filesystem import render_fs_page
                self._send_html(render_fs_page())
            elif path == '/hsr':
                from templates.hsr import render_hsr_page
                self._send_html(render_hsr_page())
            elif path == '/backup':
                from templates.backup import render_backup_page
                self._send_html(render_backup_page())
            else:
                self._send_html(self._error_page('Page not found'), 404)
        except Exception:
            self._send_html(self._error_page(traceback.format_exc()), 500)

    def do_POST(self):
        params = self._read_post_params()
        path = self.path
        try:
            if path == '/fs/check':
                from handlers.filesystem import run_check
                self._send_html(run_check(params))
            elif path == '/fs/extend':
                from handlers.filesystem import run_extend
                self._send_html(run_extend(params))
            elif path == '/hsr/check':
                from handlers.hsr import run_check
                self._send_html(run_check(params))
            elif path == '/backup/trigger':
                from handlers.backup import run_trigger
                self._send_html(run_trigger(params))
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
    def server_bind(self):
        # Skip socket.getfqdn() — it does a reverse DNS lookup on 0.0.0.0
        # which hangs on RHEL hosts with slow or missing DNS.
        import socketserver
        socketserver.TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]

    def process_request(self, request, client_address):
        t = threading.Thread(target=self.finish_request,
                             args=(request, client_address), daemon=True)
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
PYEOF

# ── config.ini ─────────────────────────────────────────────
cat > "${INSTALL_DIR}/config.ini" << 'EOF'
[server]
port = 8080
host = 0.0.0.0

[ansible]
playbook_dir = ansible/playbooks
inventory    = ansible/inventory/hosts.ini
timeout      = 300

[paths]
tmp_dir = /tmp/sap_mgmt
db_path = db/audit.db

[systems]
# Format: SID:hostname:instance_number:role  (comma-separated)
# role = primary | secondary
# Example:
# hosts = S4H:hana-node1:00:primary, S4H:hana-node2:00:secondary
hosts =
EOF

# ── config.py ──────────────────────────────────────────────
cat > "${INSTALL_DIR}/config.py" << 'PYEOF'
import configparser
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_config = None


def get_config():
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        _config.read(os.path.join(_BASE_DIR, 'config.ini'))
    return _config


def get_systems():
    raw = get_config().get('systems', 'hosts', fallback='')
    systems = []
    for entry in raw.split(','):
        entry = entry.strip()
        if not entry:
            continue
        parts = [p.strip() for p in entry.split(':')]
        if len(parts) >= 4:
            systems.append({'sid': parts[0], 'host': parts[1],
                            'instance': parts[2], 'role': parts[3]})
    return systems


def get_ansible_cfg():
    cfg = get_config()
    base = _BASE_DIR
    return {
        'playbook_dir': os.path.join(base, cfg.get('ansible', 'playbook_dir',
                                                    fallback='ansible/playbooks')),
        'inventory':    os.path.join(base, cfg.get('ansible', 'inventory',
                                                   fallback='ansible/inventory/hosts.ini')),
        'timeout':      int(cfg.get('ansible', 'timeout', fallback='300')),
        'tmp_dir':      cfg.get('paths', 'tmp_dir', fallback='/tmp/sap_mgmt'),
    }
PYEOF

# ── runner.py ──────────────────────────────────────────────
cat > "${INSTALL_DIR}/runner.py" << 'PYEOF'
"""Thin wrapper around ansible-playbook subprocess calls."""
import subprocess
import os
from config import get_ansible_cfg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_playbook(playbook, extra_vars=None, limit=None):
    cfg = get_ansible_cfg()
    cmd = ['ansible-playbook',
           os.path.join(cfg['playbook_dir'], playbook),
           '-i', cfg['inventory']]
    if limit:
        cmd += ['--limit', limit]
    if extra_vars:
        for k, v in extra_vars.items():
            cmd += ['-e', f'{k}={v}']
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=cfg['timeout'], cwd=BASE_DIR)
PYEOF

# ── db/audit.py ────────────────────────────────────────────
cat > "${INSTALL_DIR}/db/audit.py" << 'PYEOF'
import sqlite3
import os
import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(_BASE_DIR, 'db', 'audit.db')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                action    TEXT    NOT NULL,
                target    TEXT,
                success   INTEGER,
                details   TEXT
            )
        """)
        conn.commit()


def log_action(action, target, success, details=''):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp,action,target,success,details) "
            "VALUES (?,?,?,?,?)",
            (datetime.datetime.now().isoformat(), action, target,
             1 if success else 0, details))
        conn.commit()
PYEOF

# ── templates/base.py ──────────────────────────────────────
cat > "${INSTALL_DIR}/templates/base.py" << 'PYEOF'
def render(title, content, active_nav=''):
    nav_items = [('/', 'Dashboard', 'dashboard'), ('/fs', 'Filesystem', 'fs'),
                 ('/hsr', 'HSR Status', 'hsr'), ('/backup', 'Backup', 'backup')]
    nav_links = ''
    for href, label, key in nav_items:
        active = 'background:#154360;' if active_nav == key else ''
        nav_links += (f'<a href="{href}" style="color:white;text-decoration:none;'
                      f'padding:12px 22px;display:inline-block;{active}">{label}</a>\n')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - SAP Landscape Manager</title>
<style>
*{{box-sizing:border-box;}}
body{{font-family:Arial,sans-serif;margin:0;background:#f0f2f5;color:#333;}}
nav{{background:#1a5276;display:flex;align-items:center;}}
.brand{{color:white;font-weight:bold;padding:12px 24px;font-size:1.05em;border-right:1px solid #154360;white-space:nowrap;}}
.container{{padding:24px;max-width:1280px;margin:0 auto;}}
h2{{color:#1a5276;margin-top:0;}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:4px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.12);}}
th{{background:#1a5276;color:white;padding:11px 14px;text-align:left;font-size:.92em;}}
td{{padding:10px 14px;border-bottom:1px solid #eee;font-size:.92em;}}
tr:last-child td{{border-bottom:none;}}
tr:hover td{{background:#f8f9fa;}}
.btn{{padding:7px 16px;border:none;border-radius:3px;cursor:pointer;font-size:.9em;text-decoration:none;display:inline-block;}}
.btn-primary{{background:#1a5276;color:white;}}
.btn-warning{{background:#e67e22;color:white;}}
.btn-danger{{background:#c0392b;color:white;}}
.btn-success{{background:#1e8449;color:white;}}
.btn-sm{{padding:4px 10px;font-size:.82em;}}
.alert{{padding:12px 16px;border-radius:4px;margin:12px 0;font-size:.92em;}}
.alert-danger{{background:#fdedec;border-left:4px solid #e74c3c;}}
.alert-warning{{background:#fef9e7;border-left:4px solid #f39c12;}}
.alert-success{{background:#eafaf1;border-left:4px solid #27ae60;}}
.alert-info{{background:#eaf4fb;border-left:4px solid #2980b9;}}
.card{{background:white;border-radius:4px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.12);margin-bottom:20px;}}
.badge{{padding:3px 9px;border-radius:12px;font-size:.8em;color:white;font-weight:bold;}}
.badge-danger{{background:#c0392b;}}
.badge-warning{{background:#e67e22;}}
.badge-ok{{background:#1e8449;}}
.badge-info{{background:#2980b9;}}
input[type=text],input[type=number],select{{padding:6px 10px;border:1px solid #ccc;border-radius:3px;font-size:.9em;}}
label{{font-size:.9em;color:#555;display:block;margin-bottom:3px;}}
.form-row{{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap;margin-bottom:16px;}}
.form-group{{display:flex;flex-direction:column;}}
pre{{background:#2c3e50;color:#ecf0f1;padding:14px;border-radius:4px;font-size:.82em;overflow-x:auto;white-space:pre-wrap;margin:0;}}
code{{background:#eee;padding:1px 5px;border-radius:3px;font-size:.9em;}}
.stat-box{{background:white;border-radius:4px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.12);flex:1;min-width:180px;}}
.stat-num{{font-size:2.2em;font-weight:bold;color:#1a5276;}}
.stat-lbl{{color:#888;font-size:.9em;margin-bottom:12px;}}
</style>
</head>
<body>
<nav>
  <div class="brand">SAP Landscape Manager</div>
  {nav_links}
</nav>
<div class="container">
  <h2>{title}</h2>
  {content}
</div>
</body>
</html>"""
PYEOF

# ── templates/dashboard.py ─────────────────────────────────
cat > "${INSTALL_DIR}/templates/dashboard.py" << 'PYEOF'
from templates.base import render
from config import get_systems


def render_dashboard():
    systems = get_systems()
    rows = ''
    for s in systems:
        role_cls = 'badge-danger' if s['role'] == 'primary' else 'badge-info'
        rows += (f'<tr><td><strong>{s["sid"]}</strong></td>'
                 f'<td><code>{s["host"]}</code></td><td>{s["instance"]}</td>'
                 f'<td><span class="badge {role_cls}">{s["role"].upper()}</span></td></tr>\n')
    if not rows:
        rows = ('<tr><td colspan="4" style="color:#888;text-align:center;">'
                'No systems configured — edit <code>config.ini</code> → [systems] hosts.</td></tr>')
    table = (f'<div class="card"><strong>Registered SAP HANA Systems</strong>'
             f'<p style="color:#666;font-size:.9em;margin:4px 0 14px;">'
             f'Edit <code>config.ini</code> under <code>[systems]</code> to add or remove hosts.</p>'
             f'<table><thead><tr><th>SID</th><th>Host</th><th>Instance</th><th>Role</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>')
    cards = (f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;">'
             f'<div class="stat-box"><div class="stat-num">{len(systems)}</div>'
             f'<div class="stat-lbl">Registered Systems</div>'
             f'<a href="/fs" class="btn btn-primary">Check Filesystems</a></div>'
             f'<div class="stat-box"><div class="stat-num">HSR</div>'
             f'<div class="stat-lbl">Replication Status</div>'
             f'<a href="/hsr" class="btn btn-primary">Check HSR</a></div>'
             f'<div class="stat-box"><div class="stat-num">BKP</div>'
             f'<div class="stat-lbl">Backup Console</div>'
             f'<a href="/backup" class="btn btn-primary">Open Console</a></div></div>')
    return render('Dashboard', table + cards, active_nav='dashboard')
PYEOF

# ── templates/filesystem.py ────────────────────────────────
cat > "${INSTALL_DIR}/templates/filesystem.py" << 'PYEOF'
from templates.base import render


def render_fs_page(error=None, target='all', threshold=80):
    err = (f'<div class="alert alert-danger"><strong>Ansible error:</strong>'
           f'<br><pre>{error}</pre></div>') if error else ''
    content = (f'{err}<div class="card">'
               f'<p style="color:#666;font-size:.9em;margin-top:0;">'
               f'Runs <code>df -P</code> on all HANA hosts via Ansible and lists '
               f'filesystems above the threshold. LVM volumes have a one-click extend action.</p>'
               f'<form method="POST" action="/fs/check"><div class="form-row">'
               f'<div class="form-group"><label>Target (hostname or "all")</label>'
               f'<input type="text" name="target" value="{target}" placeholder="all"></div>'
               f'<div class="form-group"><label>Threshold (%)</label>'
               f'<input type="number" name="threshold" value="{threshold}" '
               f'min="50" max="99" style="width:80px;"></div>'
               f'<button type="submit" class="btn btn-primary">Run Check</button>'
               f'</div></form></div>')
    return render('Filesystem Check', content, active_nav='fs')


def render_fs_results(filesystems, target='all', threshold=80):
    rerun = (f'<div class="card"><form method="POST" action="/fs/check">'
             f'<div class="form-row">'
             f'<div class="form-group"><label>Target</label>'
             f'<input type="text" name="target" value="{target}"></div>'
             f'<div class="form-group"><label>Threshold (%)</label>'
             f'<input type="number" name="threshold" value="{threshold}" '
             f'min="50" max="99" style="width:80px;"></div>'
             f'<button type="submit" class="btn btn-primary">Re-run Check</button>'
             f'</div></form></div>')
    if not filesystems:
        return render('Filesystem Check',
                      rerun + f'<div class="alert alert-success">No filesystems above '
                              f'{threshold}% on <strong>{target}</strong>.</div>',
                      active_nav='fs')
    rows = ''
    for fs in filesystems:
        pct = fs['use_pct']
        badge = 'badge-danger' if pct >= 90 else 'badge-warning'
        is_lvm = fs['device'].startswith('/dev/mapper/')
        if is_lvm:
            btn = (f'<form method="POST" action="/fs/extend" style="display:inline;" '
                   f'onsubmit="return confirm(\'Extend {fs[chr(109)+"ount"]} on {fs["host"]} by 10G?\');">'
                   f'<input type="hidden" name="host"        value="{fs["host"]}">'
                   f'<input type="hidden" name="mount_point" value="{fs["mount"]}">'
                   f'<input type="hidden" name="lv_path"     value="{fs["device"]}">'
                   f'<input type="hidden" name="extend_size" value="10G">'
                   f'<input type="hidden" name="fs_type"     value="xfs">'
                   f'<button type="submit" class="btn btn-warning btn-sm">Extend +10G</button></form>')
        else:
            btn = '<span style="color:#aaa;font-size:.82em;">non-LVM</span>'
        rows += (f'<tr><td><code>{fs["host"]}</code></td><td><code>{fs["mount"]}</code></td>'
                 f'<td><code>{fs["device"]}</code></td><td>{fs["size"]}</td>'
                 f'<td>{fs["used"]}</td><td>{fs["avail"]}</td>'
                 f'<td><span class="badge {badge}">{pct}%</span></td>'
                 f'<td>{btn}</td></tr>\n')
    alert = (f'<div class="alert alert-warning">Found <strong>{len(filesystems)}</strong> '
             f'filesystem(s) above {threshold}% on <strong>{target}</strong>.</div>')
    table = (f'<table><thead><tr><th>Host</th><th>Mount</th><th>Device</th>'
             f'<th>Size</th><th>Used</th><th>Free</th><th>Use%</th><th>Action</th>'
             f'</tr></thead><tbody>{rows}</tbody></table>')
    return render('Filesystem Check', rerun + alert + table, active_nav='fs')


def render_extend_result(success, host, lv_path, mount_point, extend_size, new_size, error):
    if success:
        detail = f'<br>New usage: <code>{new_size}</code>' if new_size else ''
        msg = (f'<div class="alert alert-success"><strong>Extended successfully.</strong><br>'
               f'Host: <code>{host}</code> &nbsp;|&nbsp; LV: <code>{lv_path}</code> &nbsp;|&nbsp; '
               f'Mount: <code>{mount_point}</code> &nbsp;|&nbsp; Added: <strong>+{extend_size}</strong>'
               f'{detail}</div>')
    else:
        msg = (f'<div class="alert alert-danger"><strong>Extend failed.</strong><br>'
               f'Host: <code>{host}</code> &nbsp;|&nbsp; LV: <code>{lv_path}</code><br>'
               f'<pre>{error}</pre></div>')
    return render('Filesystem – Extend Result',
                  msg + '<a href="/fs" class="btn btn-primary">Back to Filesystem Check</a>',
                  active_nav='fs')
PYEOF

# ── templates/hsr.py ───────────────────────────────────────
cat > "${INSTALL_DIR}/templates/hsr.py" << 'PYEOF'
from templates.base import render


def render_hsr_page(error=None, results=None):
    err = (f'<div class="alert alert-danger"><strong>Ansible error:</strong>'
           f'<br><pre>{error}</pre></div>') if error else ''
    form = ('<div class="card"><p style="color:#666;font-size:.9em;margin-top:0;">'
            'Runs <code>hdbnsutil -sr_state</code> on each primary HANA host via Ansible.</p>'
            '<form method="POST" action="/hsr/check">'
            '<button type="submit" class="btn btn-primary">Check HSR Status</button>'
            '</form></div>')
    if results is None:
        return render('HSR Status', form + err, active_nav='hsr')
    if not results:
        return render('HSR Status',
                      form + err + '<div class="alert alert-info">No results — check '
                                   '<code>ansible/inventory/hosts.ini</code> hana_primary group.</div>',
                      active_nav='hsr')
    rows = ''
    for r in results:
        status = r.get('status', 'UNKNOWN')
        badge = {'ACTIVE': 'badge-ok', 'INITIALIZING': 'badge-warning',
                 'SYNCING': 'badge-warning', 'ERROR': 'badge-danger'}.get(status, 'badge-warning')
        rows += (f'<tr><td><strong>{r.get("sid","")}</strong></td>'
                 f'<td><code>{r.get("host","")}</code></td><td>{r.get("site","")}</td>'
                 f'<td>{r.get("mode","")}</td>'
                 f'<td><span class="badge {badge}">{status}</span></td>'
                 f'<td style="font-size:.82em;color:#666;">{r.get("last_update","")}</td></tr>\n')
    table = (f'<table><thead><tr><th>SID</th><th>Host</th><th>Site</th>'
             f'<th>Mode</th><th>Status</th><th>Checked At</th></tr></thead>'
             f'<tbody>{rows}</tbody></table>')
    return render('HSR Status', form + err + table, active_nav='hsr')
PYEOF

# ── templates/backup.py ────────────────────────────────────
cat > "${INSTALL_DIR}/templates/backup.py" << 'PYEOF'
from templates.base import render


def render_backup_page(message=None, msg_type='info'):
    msg = f'<div class="alert alert-{msg_type}">{message}</div>' if message else ''
    content = (f'{msg}<div class="alert alert-info"><strong>Phase 2 – Backup Console</strong><br>'
               f'Planned: view HANA backup catalog, trigger DATA backup, re-run failed backups, '
               f'check Backint status.</div>'
               f'<a href="/" class="btn btn-primary">Back to Dashboard</a>')
    return render('Backup Console', content, active_nav='backup')
PYEOF

# ── handlers/filesystem.py ─────────────────────────────────
cat > "${INSTALL_DIR}/handlers/filesystem.py" << 'PYEOF'
import glob
import os
from runner import run_playbook
from config import get_ansible_cfg
from db.audit import log_action
from templates.filesystem import render_fs_page, render_fs_results, render_extend_result


def run_check(params):
    target    = params.get('target',    ['all'])[0].strip() or 'all'
    threshold = params.get('threshold', ['80'])[0].strip()  or '80'
    cfg = get_ansible_cfg()
    tmp = cfg['tmp_dir']
    os.makedirs(tmp, exist_ok=True)
    for f in glob.glob(os.path.join(tmp, 'fs_*.txt')):
        os.remove(f)
    result = run_playbook('check_filesystem.yml',
                          extra_vars={'threshold': threshold},
                          limit=None if target == 'all' else target)
    log_action('fs_check', target, result.returncode == 0, f'threshold={threshold}')
    if result.returncode != 0:
        return render_fs_page(error=result.stderr or result.stdout,
                              target=target, threshold=int(threshold))
    filesystems = []
    for filepath in sorted(glob.glob(os.path.join(tmp, 'fs_*.txt'))):
        hostname = os.path.basename(filepath)[3:-4]
        with open(filepath) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) < 6:
                    continue
                filesystems.append({'host': hostname, 'device': parts[0],
                                    'size': parts[1], 'used': parts[2],
                                    'avail': parts[3],
                                    'use_pct': int(parts[4]) if parts[4].isdigit() else 0,
                                    'mount': parts[5]})
    return render_fs_results(filesystems, target=target, threshold=int(threshold))


def run_extend(params):
    host        = params.get('host',        [''])[0].strip()
    mount_point = params.get('mount_point', [''])[0].strip()
    lv_path     = params.get('lv_path',     [''])[0].strip()
    extend_size = params.get('extend_size', ['10G'])[0].strip() or '10G'
    fs_type     = params.get('fs_type',     ['xfs'])[0].strip() or 'xfs'
    if not all([host, mount_point, lv_path]):
        return render_fs_page(error='Missing required parameters: host, mount_point, lv_path')
    cfg = get_ansible_cfg()
    tmp = cfg['tmp_dir']
    os.makedirs(tmp, exist_ok=True)
    result_file = os.path.join(tmp, f'extend_result_{host}.txt')
    if os.path.exists(result_file):
        os.remove(result_file)
    result = run_playbook('extend_lvm.yml',
                          extra_vars={'target_host': host, 'lv_path': lv_path,
                                      'mount_point': mount_point, 'extend_size': extend_size,
                                      'fs_type': fs_type})
    log_action('fs_extend', host, result.returncode == 0,
               f'lv={lv_path} mount={mount_point} size=+{extend_size}')
    new_size = ''
    if os.path.exists(result_file):
        with open(result_file) as fh:
            new_size = fh.read().strip()
    return render_extend_result(result.returncode == 0, host, lv_path, mount_point,
                                extend_size, new_size, result.stderr or result.stdout)
PYEOF

# ── handlers/hsr.py ────────────────────────────────────────
cat > "${INSTALL_DIR}/handlers/hsr.py" << 'PYEOF'
import glob
import os
import datetime
from runner import run_playbook
from config import get_ansible_cfg, get_systems
from db.audit import log_action
from templates.hsr import render_hsr_page


def run_check(params):
    cfg = get_ansible_cfg()
    tmp = cfg['tmp_dir']
    os.makedirs(tmp, exist_ok=True)
    for f in glob.glob(os.path.join(tmp, 'hsr_*.txt')):
        os.remove(f)
    result = run_playbook('check_hsr.yml')
    log_action('hsr_check', 'hana_primary', result.returncode == 0, f'rc={result.returncode}')
    if result.returncode != 0:
        return render_hsr_page(error=result.stderr or result.stdout)
    host_map = {s['host']: s for s in get_systems()}
    results = []
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for filepath in sorted(glob.glob(os.path.join(tmp, 'hsr_*.txt'))):
        hostname = os.path.basename(filepath)[4:-4]
        sys_info = host_map.get(hostname, {})
        with open(filepath) as fh:
            raw = fh.read()
        status, site, mode = 'UNKNOWN', '', ''
        for line in raw.splitlines():
            line = line.strip()
            low = line.lower()
            if 'mode:' in low:
                mode = line.split(':', 1)[-1].strip()
            if 'site name:' in low or 'sitename:' in low:
                site = line.split(':', 1)[-1].strip()
            if status == 'UNKNOWN':
                if 'ACTIVE'        in line: status = 'ACTIVE'
                elif 'ERROR'       in line: status = 'ERROR'
                elif 'INITIALIZING' in line: status = 'INITIALIZING'
                elif 'SYNCING'     in line: status = 'SYNCING'
        results.append({'sid': sys_info.get('sid', ''), 'host': hostname,
                        'site': site, 'mode': mode, 'status': status, 'last_update': now})
    return render_hsr_page(results=results)
PYEOF

# ── handlers/backup.py ─────────────────────────────────────
cat > "${INSTALL_DIR}/handlers/backup.py" << 'PYEOF'
from templates.backup import render_backup_page


def run_trigger(params):
    return render_backup_page(message='Backup console coming in Phase 2.', msg_type='info')
PYEOF

# ── ansible/ansible.cfg ────────────────────────────────────
cat > "${INSTALL_DIR}/ansible/ansible.cfg" << 'EOF'
[defaults]
inventory         = inventory/hosts.ini
host_key_checking = False
timeout           = 30
stdout_callback   = default
remote_user       = root
private_key_file  = ~/.ssh/id_rsa
forks             = 10

[privilege_escalation]
become        = True
become_method = sudo
become_user   = root
EOF

# ── ansible/inventory/hosts.ini ────────────────────────────
cat > "${INSTALL_DIR}/ansible/inventory/hosts.ini" << 'EOF'
# SAP HANA Landscape Inventory
# Uncomment and edit to match your environment.

[hana_primary]
# hana-node1   sid=S4H  instance=00  ansible_user=root
# ecc-hana     sid=ECC  instance=01  ansible_user=root

[hana_secondary]
# hana-node2   sid=S4H  instance=00  ansible_user=root

[all_hana:children]
hana_primary
hana_secondary

[all_hana:vars]
ansible_ssh_private_key_file = ~/.ssh/id_rsa
ansible_python_interpreter   = /usr/bin/python3
EOF

# ── ansible/playbooks/check_filesystem.yml ─────────────────
cat > "${INSTALL_DIR}/ansible/playbooks/check_filesystem.yml" << 'EOF'
---
- name: Check filesystem usage on HANA hosts
  hosts: "{{ target | default('all_hana') }}"
  gather_facts: false
  become: true

  vars:
    threshold: 80
    tmp_dir: /tmp/sap_mgmt

  pre_tasks:
    - name: Ensure result directory exists on management server
      local_action:
        module: file
        path: "{{ tmp_dir }}"
        state: directory
        mode: '0755'
      become: false
      run_once: true

  tasks:
    - name: Collect filesystems above {{ threshold }}%
      shell: >
        df -P | awk -v t="{{ threshold }}" '
          NR>1 {
            gsub(/%/, "", $5)
            if ($5+0 >= t+0)
              printf "%s|%s|%s|%s|%s|%s\n", $1, $2, $3, $4, $5, $6
          }
        '
      register: df_out
      changed_when: false

    - name: Write results to management server
      local_action:
        module: copy
        content: "{{ df_out.stdout }}\n"
        dest: "{{ tmp_dir }}/fs_{{ inventory_hostname }}.txt"
      become: false
EOF

# ── ansible/playbooks/extend_lvm.yml ──────────────────────
cat > "${INSTALL_DIR}/ansible/playbooks/extend_lvm.yml" << 'EOF'
---
- name: Extend LVM filesystem
  hosts: "{{ target_host }}"
  gather_facts: false
  become: true

  vars:
    fs_type: xfs
    tmp_dir: /tmp/sap_mgmt

  tasks:
    - name: Confirm LV exists
      command: lvdisplay {{ lv_path }}
      changed_when: false

    - name: Extend logical volume by {{ extend_size }}
      command: lvextend -L +{{ extend_size }} {{ lv_path }}

    - name: Grow XFS filesystem online
      command: xfs_growfs {{ mount_point }}
      when: fs_type == 'xfs'

    - name: Grow ext4 filesystem online
      command: resize2fs {{ lv_path }}
      when: fs_type == 'ext4'

    - name: Verify new filesystem size
      shell: df -h {{ mount_point }} | awk 'NR>1'
      register: new_size
      changed_when: false

    - name: Write result to management server
      local_action:
        module: copy
        content: "{{ new_size.stdout }}\n"
        dest: "{{ tmp_dir }}/extend_result_{{ inventory_hostname }}.txt"
      become: false
EOF

# ── ansible/playbooks/check_hsr.yml ───────────────────────
cat > "${INSTALL_DIR}/ansible/playbooks/check_hsr.yml" << 'EOF'
---
- name: Check HANA System Replication status
  hosts: hana_primary
  gather_facts: false
  become: true

  vars:
    tmp_dir: /tmp/sap_mgmt

  pre_tasks:
    - name: Ensure result directory exists on management server
      local_action:
        module: file
        path: "{{ tmp_dir }}"
        state: directory
        mode: '0755'
      become: false
      run_once: true

  tasks:
    - name: Get HSR state via hdbnsutil
      shell: |
        source /usr/sap/{{ sid }}/home/.sapenv.sh 2>/dev/null || true
        hdbnsutil -sr_state
      args:
        executable: /bin/bash
      become_user: "{{ sid | lower }}adm"
      register: hsr_out
      changed_when: false

    - name: Write HSR state to management server
      local_action:
        module: copy
        content: "{{ hsr_out.stdout }}\n"
        dest: "{{ tmp_dir }}/hsr_{{ inventory_hostname }}.txt"
      become: false
EOF

# ── systemd service ────────────────────────────────────────
cat > "${INSTALL_DIR}/systemd/sap-mgmt.service" << EOF
[Unit]
Description=SAP Landscape Manager
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=SAP_MGMT_PORT=8080

[Install]
WantedBy=multi-user.target
EOF

# ── Permissions ────────────────────────────────────────────
chmod +x "${INSTALL_DIR}/server.py"

# ── Self-test ──────────────────────────────────────────────
echo ""
echo "[4/4] Running self-test..."
cd "${INSTALL_DIR}"
python3 -c "
import sys
sys.path.insert(0, '.')
from config import get_config, get_systems
from db.audit import init_db
from templates.base import render
from templates.dashboard import render_dashboard
from templates.filesystem import render_fs_page
from templates.hsr import render_hsr_page
init_db()
render_dashboard()
render_fs_page()
render_hsr_page()
print('  All modules OK')
"

# ── Next steps ─────────────────────────────────────────────
echo ""
echo "======================================================"
echo " Bootstrap complete!"
echo "======================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Add your HANA hosts to config.ini:"
echo "       ${INSTALL_DIR}/config.ini  → [systems] hosts"
echo ""
echo "  2. Add your HANA hosts to Ansible inventory:"
echo "       ${INSTALL_DIR}/ansible/inventory/hosts.ini"
echo ""
echo "  3. Make sure SSH key auth works to all HANA hosts:"
echo "       ssh-keygen -t rsa -b 4096      # if no key yet"
echo "       ssh-copy-id root@<hana-host>"
echo ""
echo "  4. Start the server:"
echo "       cd ${INSTALL_DIR} && python3 server.py"
echo ""
echo "  5. (Optional) Install as a systemd service:"
echo "       cp ${INSTALL_DIR}/systemd/sap-mgmt.service /etc/systemd/system/"
echo "       systemctl daemon-reload"
echo "       systemctl enable --now sap-mgmt"
echo ""
echo "  Access: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
