from templates.base import render


def render_hsr_page(error=None, results=None):
    err_html = (
        f'<div class="alert alert-danger"><strong>Ansible error:</strong><br><pre>{error}</pre></div>'
        if error else ''
    )

    form = """
<div class="card">
  <p style="color:#666;font-size:.9em;margin-top:0;">
    Runs <code>hdbnsutil -sr_state</code> on each primary HANA host via Ansible
    and reports the replication state for each site.
  </p>
  <form method="POST" action="/hsr/check">
    <button type="submit" class="btn btn-primary">Check HSR Status</button>
  </form>
</div>"""

    if results is None:
        return render('HSR Status', form + err_html, active_nav='hsr')

    if not results:
        table = '<div class="alert alert-info">No HSR data collected. Check that <code>hana_primary</code> group is populated in <code>ansible/inventory/hosts.ini</code>.</div>'
    else:
        rows = ''
        for r in results:
            status = r.get('status', 'UNKNOWN')
            badge_cls = {
                'ACTIVE':       'badge-ok',
                'INITIALIZING': 'badge-warning',
                'SYNCING':      'badge-warning',
                'ERROR':        'badge-danger',
            }.get(status, 'badge-warning')

            rows += (
                f'<tr>'
                f'<td><strong>{r.get("sid","")}</strong></td>'
                f'<td><code>{r.get("host","")}</code></td>'
                f'<td>{r.get("site","")}</td>'
                f'<td>{r.get("mode","")}</td>'
                f'<td><span class="badge {badge_cls}">{status}</span></td>'
                f'<td style="font-size:.82em;color:#666;">{r.get("last_update","")}</td>'
                f'</tr>\n'
            )

        table = f"""<table>
  <thead>
    <tr><th>SID</th><th>Host</th><th>Site</th><th>Mode</th><th>Status</th><th>Checked At</th></tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

    return render('HSR Status', form + err_html + table, active_nav='hsr')
