import glob
import os
import datetime

from runner import run_playbook
from config import get_ansible_cfg, get_systems
from db.audit import log_action
from templates.hsr import render_hsr_page


def _parse_hsr_output(raw):
    """Parse hdbnsutil -sr_state output into a structured dict."""
    online        = False
    has_secondary = False
    is_suspended  = False
    site          = ''
    mode          = ''
    secondary_site  = ''
    replication_mode = ''

    for line in raw.splitlines():
        line = line.strip()
        low  = line.lower()

        if low.startswith('online:'):
            online = 'true' in low
        elif low.startswith('mode:'):
            mode = line.split(':', 1)[-1].strip()
        elif low.startswith('site name:'):
            site = line.split(':', 1)[-1].strip()
        elif low.startswith('has secondaries') and ':' in low:
            has_secondary = 'true' in low
        elif low.startswith('is primary suspended:'):
            is_suspended = 'true' in low
        elif low.startswith('replication mode of') and ':' in line:
            # e.g. "Replication mode of S41HA: sync"
            parts = line.split(':', 1)
            site_part = parts[0].split()[-1]   # site name after "of"
            rep_mode  = parts[1].strip()
            if site_part != site:              # skip the primary itself
                secondary_site   = site_part
                replication_mode = rep_mode

    # Derive human-readable status from the boolean flags
    if not online:
        status = 'OFFLINE'
    elif is_suspended:
        status = 'SUSPENDED'
    elif has_secondary:
        status = 'ACTIVE'
    else:
        status = 'NO SECONDARY'

    return {
        'site':             site,
        'mode':             mode,
        'status':           status,
        'online':           online,
        'secondary_site':   secondary_site,
        'replication_mode': replication_mode,
    }


def run_check(params):
    cfg = get_ansible_cfg()
    tmp = cfg['tmp_dir']
    os.makedirs(tmp, exist_ok=True)

    for f in glob.glob(os.path.join(tmp, 'hsr_*.txt')):
        os.remove(f)

    result = run_playbook('check_hsr.yml')
    log_action('hsr_check', 'hana_primary', result.returncode == 0,
               f'rc={result.returncode}')

    if result.returncode != 0:
        return render_hsr_page(error=result.stderr or result.stdout)

    host_map = {s['host']: s for s in get_systems()}
    results  = []
    now      = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for filepath in sorted(glob.glob(os.path.join(tmp, 'hsr_*.txt'))):
        hostname = os.path.basename(filepath)[4:-4]
        sys_info = host_map.get(hostname, {})

        with open(filepath) as fh:
            raw = fh.read()

        parsed = _parse_hsr_output(raw)
        parsed.update({
            'sid':         sys_info.get('sid', ''),
            'host':        hostname,
            'last_update': now,
        })
        results.append(parsed)

    return render_hsr_page(results=results)
