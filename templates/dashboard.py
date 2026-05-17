from templates.base import render
from config import get_systems


def render_dashboard():
    systems = get_systems()

    rows = ''
    for s in systems:
        role_cls = 'badge-danger' if s['role'] == 'primary' else 'badge-info'
        rows += (
            f'<tr>'
            f'<td><strong>{s["sid"]}</strong></td>'
            f'<td><code>{s["host"]}</code></td>'
            f'<td>{s["instance"]}</td>'
            f'<td><span class="badge {role_cls}">{s["role"].upper()}</span></td>'
            f'</tr>\n'
        )

    if not rows:
        rows = '<tr><td colspan="4" style="color:#888;text-align:center;">No systems configured. Edit <code>config.ini</code> → [systems] hosts.</td></tr>'

    system_table = f"""
<div class="card">
  <strong>Registered SAP HANA Systems</strong>
  <p style="color:#666;font-size:.9em;margin:4px 0 14px;">
    Edit <code>config.ini</code> under <code>[systems]</code> to add or remove hosts.
  </p>
  <table>
    <thead><tr><th>SID</th><th>Host</th><th>Instance</th><th>Role</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

    quick_actions = f"""
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;">
  <div class="stat-box">
    <div class="stat-num">{len(systems)}</div>
    <div class="stat-lbl">Registered Systems</div>
    <a href="/fs" class="btn btn-primary">Check Filesystems</a>
  </div>
  <div class="stat-box">
    <div class="stat-num">HSR</div>
    <div class="stat-lbl">Replication Status</div>
    <a href="/hsr" class="btn btn-primary">Check HSR</a>
  </div>
  <div class="stat-box">
    <div class="stat-num">BKP</div>
    <div class="stat-lbl">Backup Console</div>
    <a href="/backup" class="btn btn-primary">Open Console</a>
  </div>
  <div class="stat-box">
    <div class="stat-num">HC</div>
    <div class="stat-lbl">Health Check</div>
    <a href="/health" class="btn btn-primary">Run Checks</a>
  </div>
</div>"""

    return render('Dashboard', system_table + quick_actions, active_nav='dashboard')
