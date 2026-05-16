from templates.base import render


def render_fs_page(error=None, target='all', threshold=80):
    err_html = (
        f'<div class="alert alert-danger"><strong>Ansible error:</strong><br><pre>{error}</pre></div>'
        if error else ''
    )
    content = f"""{err_html}
<div class="card">
  <p style="color:#666;font-size:.9em;margin-top:0;">
    Runs <code>df -P</code> on all HANA hosts via Ansible and lists filesystems above the threshold.
    LVM volumes (<code>/dev/mapper/...</code>) have a one-click extend action.
  </p>
  <form method="POST" action="/fs/check">
    <div class="form-row">
      <div class="form-group">
        <label>Target (hostname or "all")</label>
        <input type="text" name="target" value="{target}" placeholder="all">
      </div>
      <div class="form-group">
        <label>Threshold (%)</label>
        <input type="number" name="threshold" value="{threshold}" min="50" max="99" style="width:80px;">
      </div>
      <button type="submit" class="btn btn-primary">Run Check</button>
    </div>
  </form>
</div>"""
    return render('Filesystem Check', content, active_nav='fs')


def render_fs_results(filesystems, target='all', threshold=80):
    rerun_form = f"""
<div class="card">
  <form method="POST" action="/fs/check">
    <div class="form-row">
      <div class="form-group">
        <label>Target</label>
        <input type="text" name="target" value="{target}">
      </div>
      <div class="form-group">
        <label>Threshold (%)</label>
        <input type="number" name="threshold" value="{threshold}" min="50" max="99" style="width:80px;">
      </div>
      <button type="submit" class="btn btn-primary">Re-run Check</button>
    </div>
  </form>
</div>"""

    if not filesystems:
        body = (
            rerun_form
            + f'<div class="alert alert-success">No filesystems above {threshold}% '
              f'found on <strong>{target}</strong>.</div>'
        )
        return render('Filesystem Check', body, active_nav='fs')

    rows = ''
    for fs in filesystems:
        pct = fs['use_pct']
        badge_cls = 'badge-danger' if pct >= 90 else 'badge-warning'
        is_lvm = fs['device'].startswith('/dev/mapper/')

        if is_lvm:
            extend_btn = f"""
<form method="POST" action="/fs/extend" style="display:inline;"
  onsubmit="return confirm('Extend {fs['mount']} on {fs['host']} by 10G?');">
  <input type="hidden" name="host"        value="{fs['host']}">
  <input type="hidden" name="mount_point" value="{fs['mount']}">
  <input type="hidden" name="lv_path"     value="{fs['device']}">
  <input type="hidden" name="extend_size" value="10G">
  <input type="hidden" name="fs_type"     value="xfs">
  <button type="submit" class="btn btn-warning btn-sm">Extend +10G</button>
</form>"""
        else:
            extend_btn = '<span style="color:#aaa;font-size:.82em;">non-LVM</span>'

        rows += (
            f'<tr>'
            f'<td><code>{fs["host"]}</code></td>'
            f'<td><code>{fs["mount"]}</code></td>'
            f'<td><code>{fs["device"]}</code></td>'
            f'<td>{fs["size"]}</td>'
            f'<td>{fs["used"]}</td>'
            f'<td>{fs["avail"]}</td>'
            f'<td><span class="badge {badge_cls}">{pct}%</span></td>'
            f'<td>{extend_btn}</td>'
            f'</tr>\n'
        )

    count = len(filesystems)
    alert = (
        f'<div class="alert alert-warning">Found <strong>{count}</strong> '
        f'filesystem(s) above {threshold}% on <strong>{target}</strong>.</div>'
    )
    table = f"""<table>
  <thead>
    <tr>
      <th>Host</th><th>Mount</th><th>Device</th>
      <th>Size</th><th>Used</th><th>Free</th><th>Use%</th><th>Action</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

    return render('Filesystem Check', rerun_form + alert + table, active_nav='fs')


def render_extend_result(success, host, lv_path, mount_point, extend_size, new_size, error):
    if success:
        detail = f'<br>New usage: <code>{new_size}</code>' if new_size else ''
        msg = (
            f'<div class="alert alert-success">'
            f'<strong>Extended successfully.</strong><br>'
            f'Host: <code>{host}</code> &nbsp;|&nbsp; '
            f'LV: <code>{lv_path}</code> &nbsp;|&nbsp; '
            f'Mount: <code>{mount_point}</code> &nbsp;|&nbsp; '
            f'Added: <strong>+{extend_size}</strong>{detail}'
            f'</div>'
        )
    else:
        msg = (
            f'<div class="alert alert-danger">'
            f'<strong>Extend failed.</strong><br>'
            f'Host: <code>{host}</code> &nbsp;|&nbsp; LV: <code>{lv_path}</code><br>'
            f'<pre>{error}</pre>'
            f'</div>'
        )

    content = msg + '<a href="/fs" class="btn btn-primary">Back to Filesystem Check</a>'
    return render('Filesystem – Extend Result', content, active_nav='fs')
