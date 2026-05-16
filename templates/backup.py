from templates.base import render


def render_backup_page(message=None, msg_type='info'):
    msg_html = (
        f'<div class="alert alert-{msg_type}">{message}</div>'
        if message else ''
    )

    content = f"""{msg_html}
<div class="alert alert-info">
  <strong>Phase 2 – Backup Console</strong><br>
  Planned features:
  <ul style="margin:8px 0 0;">
    <li>View HANA backup catalog (DATA, LOG, CATALOG entries via <code>hdbsql</code>)</li>
    <li>Trigger a new DATA backup and monitor its progress</li>
    <li>Re-run the most recent failed backup</li>
    <li>Check Backint agent status (for cloud backups on Azure/AWS/GCP)</li>
  </ul>
</div>
<a href="/" class="btn btn-primary">Back to Dashboard</a>"""

    return render('Backup Console', content, active_nav='backup')
