import glob
import json
import os
import datetime

from runner import run_playbook
from config import get_ansible_cfg
from db.audit import log_action
from templates.healthcheck import render_health_page, render_health_results


def start_check(params):
    from handlers.jobs import create
    return create(_run_check, params)


def _run_check(params):
    cfg = get_ansible_cfg()
    tmp = cfg['tmp_dir']
    os.makedirs(tmp, exist_ok=True)

    for f in glob.glob(os.path.join(tmp, 'health_*.json')):
        os.remove(f)

    result = run_playbook('healthcheck.yml')
    log_action('health_check', 'all_sap', result.returncode == 0,
               f'rc={result.returncode}')

    result_files = glob.glob(os.path.join(tmp, 'health_*.json'))
    if result.returncode != 0 and not result_files:
        return render_health_page(
            error=result.stderr or result.stdout)

    hosts = []
    for filepath in sorted(glob.glob(os.path.join(tmp, 'health_*.json'))):
        try:
            with open(filepath) as fh:
                data = json.load(fh)
            hosts.append(_analyse(data))
        except Exception as e:
            hosts.append({'hostname': os.path.basename(filepath),
                          'overall': 'critical', 'error': str(e), 'checks': {}})

    return render_health_results(hosts)


# ── Parsers ────────────────────────────────────────────────


def _parse_resources(raw):
    """Parse 'mem_total|mem_used|mem_pct|cpu_pct' line."""
    if not raw or raw == 'N/A':
        return {'status': 'unknown', 'cpu_pct': 0, 'mem_pct': 0, 'detail': 'N/A'}
    parts = raw.strip().split('|')
    if len(parts) < 4:
        return {'status': 'unknown', 'cpu_pct': 0, 'mem_pct': 0, 'detail': raw}
    try:
        mem_total = int(parts[0])
        mem_used  = int(parts[1])
        mem_pct   = int(parts[2])
        cpu_pct   = int(parts[3])
        if cpu_pct >= 90 or mem_pct >= 90:
            status = 'critical'
        elif cpu_pct >= 75 or mem_pct >= 80:
            status = 'warning'
        else:
            status = 'ok'
        return {
            'status':    status,
            'cpu_pct':   cpu_pct,
            'mem_pct':   mem_pct,
            'mem_used':  mem_used,
            'mem_total': mem_total,
            'detail':    f'CPU {cpu_pct}%  |  RAM {mem_used}G / {mem_total}G ({mem_pct}%)',
        }
    except Exception:
        return {'status': 'unknown', 'cpu_pct': 0, 'mem_pct': 0, 'detail': raw}


def _parse_filesystem(raw):
    """Parse pipe-delimited df output."""
    if not raw or raw == 'N/A':
        return {'status': 'unknown', 'items': [], 'detail': 'N/A'}
    items = []
    worst = 'ok'
    for line in raw.strip().splitlines():
        parts = line.split('|')
        if len(parts) < 6:
            continue
        try:
            pct = int(parts[4])
        except ValueError:
            continue
        if pct >= 90:
            item_status = 'critical'
            worst = 'critical'
        elif pct >= 80:
            item_status = 'warning'
            if worst != 'critical':
                worst = 'warning'
        else:
            item_status = 'ok'
        items.append({
            'device': parts[0], 'size': parts[1], 'used': parts[2],
            'avail': parts[3], 'pct': pct, 'mount': parts[5],
            'status': item_status,
        })
    return {'status': worst if items else 'unknown', 'items': items,
            'detail': f'{len(items)} filesystem(s) checked'}


def _parse_timesync(raw):
    if not raw or raw == 'N/A':
        return {'status': 'unknown', 'detail': 'N/A'}
    raw = raw.strip()
    try:
        offset = float(raw.split()[0])
        if abs(offset) > 1.0:
            return {'status': 'critical', 'detail': f'Offset {offset:.3f}s — too large'}
        if abs(offset) > 0.5:
            return {'status': 'warning', 'detail': f'Offset {offset:.3f}s'}
        return {'status': 'ok', 'detail': f'Offset {offset:.6f}s'}
    except Exception:
        if 'yes' in raw.lower():
            return {'status': 'ok', 'detail': 'NTP synchronized'}
        if 'no' in raw.lower() or 'unknown' in raw.lower():
            return {'status': 'warning', 'detail': 'NTP not synchronized'}
        return {'status': 'ok', 'detail': raw[:80]}


def _parse_oslogs(raw):
    if not raw or raw in ('N/A', 'no_errors', ''):
        return {'status': 'ok', 'detail': 'No recent errors', 'errors': []}
    lines = [l for l in raw.strip().splitlines() if l.strip() and l.strip() != 'no_errors']
    if not lines:
        return {'status': 'ok', 'detail': 'No recent errors', 'errors': []}
    return {
        'status': 'warning',
        'detail': f'{len(lines)} error(s) in last 2 hours',
        'errors': lines,
    }


def _parse_hdbinfo(raw):
    if not raw or raw == 'N/A':
        return {'status': 'unknown', 'detail': 'N/A', 'services': []}
    key_procs = {'hdbdaemon', 'hdbcompileserver', 'hdbindexserver',
                 'hdbpreprocessor', 'hdbwebdispatcher'}
    found = set()
    for line in raw.splitlines():
        low = line.lower()
        for p in key_procs:
            if p in low:
                found.add(p)
    missing = key_procs - found
    if missing:
        return {'status': 'warning',
                'detail': f'Missing processes: {", ".join(missing)}',
                'services': raw.strip().splitlines()}
    return {'status': 'ok',
            'detail': f'All {len(key_procs)} key HANA processes found',
            'services': raw.strip().splitlines()}


def _parse_hsr(raw):
    if not raw or raw == 'N/A':
        return {'status': 'unknown', 'detail': 'N/A'}
    online = False
    has_secondary = False
    is_suspended = False
    site = ''
    secondary = ''
    for line in raw.splitlines():
        low = line.strip().lower()
        if low.startswith('online:'):
            online = 'true' in low
        elif low.startswith('site name:'):
            site = line.split(':', 1)[-1].strip()
        elif 'has secondaries' in low and ':' in low:
            has_secondary = 'true' in low
        elif low.startswith('is primary suspended:'):
            is_suspended = 'true' in low
        elif low.startswith('replication mode of') and ':' in line:
            parts = line.split(':', 1)
            if parts[0].split()[-1] != site:
                secondary = parts[0].split()[-1]

    if not online:
        st, detail = 'critical', 'HANA is OFFLINE'
    elif is_suspended:
        st, detail = 'critical', 'Primary is SUSPENDED'
    elif has_secondary:
        st, detail = 'ok', f'ACTIVE — replicating to {secondary}'
    else:
        st, detail = 'warning', 'No secondary attached'
    return {'status': st, 'detail': detail, 'site': site, 'secondary': secondary}


def _parse_processes(raw):
    if not raw or raw == 'N/A':
        return {'status': 'unknown', 'detail': 'N/A', 'procs': []}
    procs = []
    not_green = []
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 3 and parts[0] not in ('name', 'OK', ''):
            name   = parts[0]
            color  = parts[2] if len(parts) > 2 else ''
            status = parts[3] if len(parts) > 3 else ''
            procs.append({'name': name, 'color': color, 'status': status})
            if color.upper() != 'GREEN':
                not_green.append(name)
    if not_green:
        return {'status': 'critical',
                'detail': f'Not GREEN: {", ".join(not_green)}', 'procs': procs}
    if not procs:
        return {'status': 'unknown', 'detail': 'No process data', 'procs': []}
    return {'status': 'ok',
            'detail': f'All {len(procs)} processes GREEN', 'procs': procs}


def _parse_wptable(raw):
    if not raw or raw == 'N/A':
        return {'status': 'unknown', 'detail': 'N/A', 'stopped': 0, 'total': 0}
    stopped = 0
    total = 0
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 4 and parts[0].isdigit():
            total += 1
            if parts[3].lower() in ('stop', 'stopped', 'killed'):
                stopped += 1
    if stopped:
        return {'status': 'warning', 'detail': f'{stopped}/{total} work processes stopped',
                'stopped': stopped, 'total': total}
    return {'status': 'ok', 'detail': f'{total} work processes running',
            'stopped': 0, 'total': total}


def _parse_devdisp(raw):
    if not raw or raw in ('N/A', 'no_errors', ''):
        return {'status': 'ok', 'detail': 'No errors in dev_disp'}
    lines = [l for l in raw.strip().splitlines()
             if l.strip() and l.strip() != 'no_errors']
    if not lines:
        return {'status': 'ok', 'detail': 'No errors in dev_disp'}
    return {'status': 'warning',
            'detail': f'{len(lines)} error(s) found in dev_disp', 'lines': lines}


def _analyse(data):
    role = data.get('role', 'unknown')
    checks = {}

    checks['resources']  = _parse_resources(data.get('resources', 'N/A'))
    checks['filesystem'] = _parse_filesystem(data.get('filesystem', 'N/A'))
    checks['timesync']   = _parse_timesync(data.get('timesync', 'N/A'))
    checks['oslogs']     = _parse_oslogs(data.get('oslogs', ''))

    if role in ('hana_primary', 'hana_secondary'):
        checks['hdbinfo'] = _parse_hdbinfo(data.get('hdbinfo', 'N/A'))

    if role == 'hana_primary':
        checks['hsr'] = _parse_hsr(data.get('hsr', 'N/A'))

    if role in ('ascs', 'ers', 'app_servers'):
        checks['processes'] = _parse_processes(data.get('processes', 'N/A'))

    if role == 'app_servers':
        checks['wptable']  = _parse_wptable(data.get('wptable', 'N/A'))
        checks['devdisp']  = _parse_devdisp(data.get('devdisp', ''))

    statuses = [c['status'] for c in checks.values()]
    if 'critical' in statuses:
        overall = 'critical'
    elif 'warning' in statuses:
        overall = 'warning'
    elif all(s == 'ok' for s in statuses):
        overall = 'ok'
    else:
        overall = 'unknown'

    return {
        'hostname': data.get('hostname', ''),
        'sid':      data.get('sid', ''),
        'instance': data.get('instance', ''),
        'role':     role,
        'checks':   checks,
        'overall':  overall,
        'checked_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
