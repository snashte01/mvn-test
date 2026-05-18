from templates.base import render


def render_backup_page(error=None):
    from config import get_hana_cfg
    has_stored_pw = bool(get_hana_cfg().get('system_password'))
    pw_note = (
        '<span style="color:#27ae60;font-size:.85em;">&#10003; Password stored in config.ini</span>'
        if has_stored_pw else
        '<span style="color:#888;font-size:.85em;">Not in config.ini — enter below</span>'
    )
    err_html = (
        f'<div class="alert alert-danger"><strong>Error:</strong><pre>{error}</pre></div>'
        if error else ''
    )
    pw_field = '' if has_stored_pw else """
      <div class="form-group">
        <label>HANA SYSTEM Password</label>
        <input type="password" name="hana_password" placeholder="SYSTEM password" style="width:220px;" required>
      </div>"""

    content = f"""{err_html}
<div class="card">
  <p style="color:#666;font-size:.9em;margin-top:0;">
    Connects to HANA via <code>hdbsql</code> as <strong>SYSTEM</strong> user on the primary DB node.
    Password: {pw_note}
  </p>

  <div style="display:flex;gap:20px;flex-wrap:wrap;">

    <div style="flex:1;min-width:280px;">
      <strong style="display:block;margin-bottom:10px;">View Backup Catalog</strong>
      <form method="POST" action="/backup/catalog">
        {pw_field}
        <button type="submit" class="btn btn-primary">Show Last 30 Backups</button>
      </form>
    </div>

    <div style="flex:1;min-width:280px;">
      <strong style="display:block;margin-bottom:10px;">Trigger Data Backup</strong>
      <form method="POST" action="/backup/trigger"
            onsubmit="return confirm('Trigger a full HANA data backup now? This may take minutes to hours.');">
        {pw_field}
        <div class="form-group" style="margin-top:8px;">
          <label>Backup Label (optional)</label>
          <input type="text" name="backup_label" placeholder="e.g. MANUAL_20260518" style="width:220px;">
        </div>
        <button type="submit" class="btn btn-warning" style="margin-top:10px;">Trigger Backup</button>
      </form>
    </div>

  </div>
</div>

<div class="alert alert-info" style="font-size:.88em;">
  <strong>Note:</strong> Backup runs asynchronously — the page will auto-refresh every 5 seconds while Ansible waits for HANA to complete the backup.
  Typical full backup of a 1 TB system takes 15–60 minutes.
</div>"""

    return render('Backup Console', content, active_nav='backup')


def render_backup_catalog(entries, hostname, sid, instance, hana_error=''):
    warn = (
        f'<div class="alert alert-warning"><strong>hdbsql warning:</strong><pre>{hana_error}</pre></div>'
        if hana_error else ''
    )

    if not entries:
        body = (
            warn +
            '<div class="alert alert-info">No backup catalog entries found.</div>'
            '<a href="/backup" class="btn btn-primary">Back to Backup Console</a>'
        )
        return render('Backup Catalog', body, active_nav='backup')

    _STATUS_CLS = {
        'successful': 'badge-ok',
        'running':    'badge-info',
        'failed':     'badge-danger',
        'cancel':     'badge-warning',
        'canceled':   'badge-warning',
    }
    _TYPE_ICON = {
        'complete data backup': '&#128190;',
        'data snapshot':        '&#128247;',
        'log backup':           '&#128196;',
        'log no backup':        '&#9940;',
    }

    rows = ''
    for e in entries:
        st    = e['state'].lower()
        badge = _STATUS_CLS.get(st, 'badge-warning')
        icon  = _TYPE_ICON.get(e['type'].lower(), '&#128190;')
        rows += (
            f'<tr>'
            f'<td>{icon} {e["type"]}</td>'
            f'<td><span class="badge {badge}">{e["state"]}</span></td>'
            f'<td><code>{e["start"]}</code></td>'
            f'<td><code>{e["end"]}</code></td>'
            f'<td style="font-size:.8em;color:#888;">{e["backup_id"]}</td>'
            f'<td>{e["comment"]}</td>'
            f'</tr>\n'
        )

    table = f"""<table>
  <thead>
    <tr><th>Type</th><th>State</th><th>Start</th><th>End</th><th>ID</th><th>Comment</th></tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

    header = (
        f'<div class="alert alert-success" style="margin-bottom:12px;">'
        f'Showing last {len(entries)} backup entries &nbsp;|&nbsp; '
        f'Host: <code>{hostname}</code> &nbsp;SID: <strong>{sid}</strong> &nbsp;'
        f'Instance: <strong>{instance}</strong></div>'
    )
    back = '<a href="/backup" class="btn btn-primary" style="margin-top:12px;">Back to Backup Console</a>'

    return render('Backup Catalog', warn + header + table + back, active_nav='backup')


def render_backup_trigger_result(success, output):
    if success:
        msg = (
            '<div class="alert alert-success">'
            '<strong>&#10003; Backup triggered successfully.</strong>'
            '</div>'
        )
    else:
        msg = (
            '<div class="alert alert-danger">'
            '<strong>&#10007; Backup failed or did not complete cleanly.</strong>'
            '</div>'
        )

    out_block = f'<pre>{output}</pre>' if output else ''
    back = '<a href="/backup" class="btn btn-primary" style="margin-top:12px;">Back to Backup Console</a>'
    content = msg + out_block + back
    return render('Backup – Trigger Result', content, active_nav='backup')
