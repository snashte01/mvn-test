from templates.base import render


_ROLE_LABEL = {
    'hana_primary':   'HANA Primary',
    'hana_secondary': 'HANA Secondary',
    'ascs':           'ASCS',
    'ers':            'ERS',
    'app_servers':    'App Server',
    'unknown':        'Unknown',
}

_CHECK_LABEL = {
    'resources':  'CPU/RAM',
    'filesystem': 'Disk',
    'timesync':   'Time Sync',
    'oslogs':     'OS Logs',
    'hdbinfo':    'HDB Info',
    'hsr':        'HSR',
    'processes':  'Processes',
    'wptable':    'Work Procs',
    'devdisp':    'dev_disp',
}

_STATUS_COLOR = {
    'ok':       '#1e8449',
    'warning':  '#e67e22',
    'critical': '#c0392b',
    'unknown':  '#95a5a6',
}

_STATUS_BG = {
    'ok':       '#eafaf1',
    'warning':  '#fef9e7',
    'critical': '#fdedec',
    'unknown':  '#f5f5f5',
}


def _check_box(key, check):
    label  = _CHECK_LABEL.get(key, key)
    status = check.get('status', 'unknown')
    color  = _STATUS_COLOR.get(status, '#95a5a6')
    bg     = _STATUS_BG.get(status, '#f5f5f5')
    detail = check.get('detail', '')
    icon   = {'ok': '✓', 'warning': '⚠', 'critical': '✗', 'unknown': '?'}.get(status, '?')

    extra = ''
    if key == 'filesystem' and check.get('items'):
        rows = ''
        for it in check['items']:
            c = _STATUS_COLOR.get(it['status'], '#333')
            rows += (f'<tr><td><code style="font-size:.8em;">{it["mount"]}</code></td>'
                     f'<td>{it["size"]}</td><td>{it["used"]}</td>'
                     f'<td style="color:{c};font-weight:bold;">{it["pct"]}%</td></tr>')
        extra = (f'<table style="width:100%;font-size:.82em;margin-top:6px;">'
                 f'<tr><th>Mount</th><th>Size</th><th>Used</th><th>Use%</th></tr>'
                 f'{rows}</table>')
    elif key in ('hdbinfo', 'hsr', 'processes') and check.get('services') or check.get('procs'):
        items = check.get('services', check.get('procs', []))
        if isinstance(items, list) and items:
            lines = items[:10] if isinstance(items[0], str) else [
                f"{p.get('name','')} — {p.get('color','')} {p.get('status','')}" for p in items[:10]]
            extra = f'<pre style="margin-top:6px;font-size:.78em;">{chr(10).join(lines)}</pre>'
    elif key == 'oslogs' and check.get('errors'):
        errs = chr(10).join(check['errors'][:5])
        extra = f'<pre style="margin-top:6px;font-size:.78em;">{errs}</pre>'

    return f"""
<details style="margin-bottom:8px;background:{bg};border-left:3px solid {color};
               border-radius:3px;padding:6px 10px;">
  <summary style="cursor:pointer;font-weight:bold;color:{color};font-size:.88em;list-style:none;">
    {icon} {label}
    <span style="font-weight:normal;color:#555;margin-left:8px;font-size:.92em;">{detail}</span>
  </summary>
  {extra}
</details>"""


def _host_card(host):
    overall  = host.get('overall', 'unknown')
    color    = _STATUS_COLOR.get(overall, '#95a5a6')
    bg       = _STATUS_BG.get(overall, '#f5f5f5')
    role_lbl = _ROLE_LABEL.get(host.get('role',''), host.get('role',''))
    icon     = {'ok': '●', 'warning': '◐', 'critical': '○', 'unknown': '?'}.get(overall, '?')

    checks_html = ''.join(_check_box(k, v) for k, v in host.get('checks', {}).items())

    return f"""
<div style="background:white;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.12);
            margin-bottom:16px;overflow:hidden;">
  <div style="background:{bg};border-left:5px solid {color};padding:12px 16px;
              display:flex;justify-content:space-between;align-items:center;">
    <div>
      <span style="font-size:1.1em;font-weight:bold;color:{color};">{icon}</span>
      <strong style="margin-left:8px;">{host.get('hostname','')}</strong>
      <span style="color:#666;font-size:.88em;margin-left:10px;">
        {host.get('sid','')} &nbsp;|&nbsp; {role_lbl} &nbsp;|&nbsp; Instance {host.get('instance','')}
      </span>
    </div>
    <span style="color:{color};font-weight:bold;font-size:.9em;">{overall.upper()}</span>
  </div>
  <div style="padding:12px 16px;">
    {checks_html if checks_html else '<p style="color:#aaa;font-size:.88em;">No checks collected.</p>'}
    <div style="color:#aaa;font-size:.78em;margin-top:4px;">Checked at {host.get('checked_at','')}</div>
  </div>
</div>"""


def render_health_page(error=None):
    err = (f'<div class="alert alert-danger"><strong>Error:</strong><pre>{error}</pre></div>'
           if error else '')
    content = f"""{err}
<div class="card">
  <p style="color:#666;font-size:.9em;margin-top:0;">
    Runs comprehensive checks across all SAP landscape hosts via Ansible:
    CPU/RAM, disk, time sync, OS logs, HANA services, HSR replication,
    SAP process list, work processes, and dev_disp errors.
  </p>
  <form method="POST" action="/health/check">
    <button type="submit" class="btn btn-primary">Run Health Check</button>
  </form>
</div>"""
    return render('SAP Health Check', content, active_nav='health')


def render_health_results(hosts):
    if not hosts:
        return render('SAP Health Check',
                      '<div class="alert alert-info">No results collected.</div>',
                      active_nav='health')

    ok_count       = sum(1 for h in hosts if h['overall'] == 'ok')
    warn_count     = sum(1 for h in hosts if h['overall'] == 'warning')
    critical_count = sum(1 for h in hosts if h['overall'] == 'critical')

    summary = f"""
<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;">
  <div class="stat-box" style="min-width:120px;text-align:center;">
    <div class="stat-num">{len(hosts)}</div>
    <div class="stat-lbl">Hosts checked</div>
  </div>
  <div class="stat-box" style="min-width:120px;text-align:center;border-left:4px solid #1e8449;">
    <div class="stat-num" style="color:#1e8449;">{ok_count}</div>
    <div class="stat-lbl">Healthy</div>
  </div>
  <div class="stat-box" style="min-width:120px;text-align:center;border-left:4px solid #e67e22;">
    <div class="stat-num" style="color:#e67e22;">{warn_count}</div>
    <div class="stat-lbl">Warnings</div>
  </div>
  <div class="stat-box" style="min-width:120px;text-align:center;border-left:4px solid #c0392b;">
    <div class="stat-num" style="color:#c0392b;">{critical_count}</div>
    <div class="stat-lbl">Critical</div>
  </div>
  <div style="flex:1;display:flex;align-items:flex-end;justify-content:flex-end;">
    <form method="POST" action="/health/check">
      <button type="submit" class="btn btn-primary">Re-run Check</button>
    </form>
  </div>
</div>"""

    order = {'critical': 0, 'warning': 1, 'ok': 2, 'unknown': 3}
    sorted_hosts = sorted(hosts, key=lambda h: order.get(h['overall'], 3))
    cards = ''.join(_host_card(h) for h in sorted_hosts)

    return render('SAP Health Check', summary + cards, active_nav='health')
