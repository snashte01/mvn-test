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
        table = ('<div class="alert alert-info">No HSR data collected. '
                 'Check that <code>hana_primary</code> group is populated '
                 'in <code>ansible/inventory/hosts.ini</code>.</div>')
    else:
        rows = ''
        for r in results:
            status = r.get('status', 'UNKNOWN')
            badge_cls = {
                'ACTIVE':       'badge-ok',
                'OFFLINE':      'badge-danger',
                'SUSPENDED':    'badge-danger',
                'NO SECONDARY': 'badge-warning',
            }.get(status, 'badge-warning')

            online_dot = (
                '<span style="color:#1e8449;font-size:1.2em;">&#9679;</span>'
                if r.get('online') else
                '<span style="color:#c0392b;font-size:1.2em;">&#9679;</span>'
            )

            secondary = r.get('secondary_site', '')
            rep_mode  = r.get('replication_mode', '')
            sec_info  = f'{secondary} <span style="color:#888;font-size:.82em;">({rep_mode})</span>' if secondary else '—'

            rows += (
                f'<tr>'
                f'<td><strong>{r.get("sid","")}</strong></td>'
                f'<td><code>{r.get("host","")}</code></td>'
                f'<td>{r.get("site","")}</td>'
                f'<td>{r.get("mode","")}</td>'
                f'<td>{sec_info}</td>'
                f'<td>{online_dot} <span class="badge {badge_cls}">{status}</span></td>'
                f'<td style="font-size:.82em;color:#666;">{r.get("last_update","")}</td>'
                f'</tr>\n'
            )

        table = f"""<table>
  <thead>
    <tr>
      <th>SID</th><th>Host</th><th>Primary Site</th><th>Mode</th>
      <th>Secondary Site</th><th>Status</th><th>Checked At</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

    return render('HSR Status', form + err_html + table, active_nav='hsr')
