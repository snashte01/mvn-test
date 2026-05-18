import csv
import io
import json
import os

from runner import run_playbook
from config import get_ansible_cfg, get_hana_cfg
from db.audit import log_action
from templates.backup import (
    render_backup_page,
    render_backup_catalog,
    render_backup_trigger_result,
)


def start_catalog(params):
    from handlers.jobs import create
    return create(_run_catalog, params)


def start_trigger(params):
    from handlers.jobs import create
    return create(_run_trigger, params)


def _hana_password(params):
    """Return HANA SYSTEM password: form param takes precedence over config."""
    pw = params.get('hana_password', [''])[0].strip()
    if not pw:
        pw = get_hana_cfg().get('system_password', '')
    return pw


def _run_catalog(params):
    pw = _hana_password(params)
    if not pw:
        return render_backup_page(
            error='HANA SYSTEM password is required. Enter it in the form or set [hana] system_password in config.ini.')

    cfg = get_ansible_cfg()
    os.makedirs(cfg['tmp_dir'], exist_ok=True)
    result_file = os.path.join(cfg['tmp_dir'], 'backup_catalog.json')
    if os.path.exists(result_file):
        os.remove(result_file)

    result = run_playbook('backup_catalog.yml',
                          secure_vars={'hana_system_password': pw})
    log_action('backup_catalog', 'hana_primary', result.returncode == 0,
               f'rc={result.returncode}')

    if not os.path.exists(result_file):
        return render_backup_page(
            error=result.stderr or result.stdout or 'Ansible produced no output.')

    with open(result_file) as fh:
        data = json.load(fh)

    entries = _parse_catalog(data.get('output', ''))
    hana_err = data.get('error', '')

    if data.get('rc', 1) != 0 and not entries:
        return render_backup_page(
            error=f"hdbsql error (rc={data.get('rc')}):\n{hana_err or data.get('output', '')}")

    return render_backup_catalog(
        entries=entries,
        hostname=data.get('hostname', ''),
        sid=data.get('sid', ''),
        instance=data.get('instance', ''),
        hana_error=hana_err if data.get('rc', 0) != 0 else '',
    )


def _run_trigger(params):
    pw = _hana_password(params)
    if not pw:
        return render_backup_page(
            error='HANA SYSTEM password is required.')

    label = params.get('backup_label', [''])[0].strip()
    cfg = get_ansible_cfg()
    os.makedirs(cfg['tmp_dir'], exist_ok=True)
    result_file = os.path.join(cfg['tmp_dir'], 'backup_trigger.json')
    if os.path.exists(result_file):
        os.remove(result_file)

    extra = {}
    if label:
        extra['backup_label'] = label

    result = run_playbook('backup_trigger.yml',
                          extra_vars=extra if extra else None,
                          secure_vars={'hana_system_password': pw})
    log_action('backup_trigger', 'hana_primary', result.returncode == 0,
               f'rc={result.returncode} label={label or "auto"}')

    if not os.path.exists(result_file):
        return render_backup_trigger_result(
            success=False,
            output=result.stderr or result.stdout,
        )

    with open(result_file) as fh:
        data = json.load(fh)

    success = data.get('rc', 1) == 0
    return render_backup_trigger_result(
        success=success,
        output=data.get('output', '') or data.get('error', ''),
    )


def _parse_catalog(raw):
    """Parse hdbsql -x -C CSV output into list of dicts."""
    if not raw or not raw.strip():
        return []
    entries = []
    reader = csv.reader(io.StringIO(raw.strip()))
    for row in reader:
        # Skip hdbsql error lines (start with * or contain no data)
        if not row or row[0].startswith('*') or row[0].startswith('0 rows'):
            continue
        if len(row) < 4:
            continue
        entries.append({
            'type':       row[0].strip('"'),
            'state':      row[1].strip('"') if len(row) > 1 else '',
            'start':      row[2].strip('"') if len(row) > 2 else '',
            'end':        row[3].strip('"') if len(row) > 3 else '',
            'backup_id':  row[4].strip('"') if len(row) > 4 else '',
            'comment':    row[5].strip('"') if len(row) > 5 else '',
        })
    return entries
