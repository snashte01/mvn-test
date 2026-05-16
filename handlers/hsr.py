import glob
import os
import datetime

from runner import run_playbook
from config import get_ansible_cfg, get_systems
from db.audit import log_action
from templates.hsr import render_hsr_page


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
    results = []
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for filepath in sorted(glob.glob(os.path.join(tmp, 'hsr_*.txt'))):
        hostname = os.path.basename(filepath)[4:-4]  # strip "hsr_" and ".txt"
        sys_info = host_map.get(hostname, {})

        with open(filepath) as fh:
            raw = fh.read()

        status, site, mode = 'UNKNOWN', '', ''
        for line in raw.splitlines():
            line = line.strip()
            low  = line.lower()
            if 'mode:' in low:
                mode = line.split(':', 1)[-1].strip()
            if 'site name:' in low or 'sitename:' in low:
                site = line.split(':', 1)[-1].strip()
            if status == 'UNKNOWN':
                if 'ACTIVE'       in line: status = 'ACTIVE'
                elif 'ERROR'      in line: status = 'ERROR'
                elif 'INITIALIZING' in line: status = 'INITIALIZING'
                elif 'SYNCING'    in line: status = 'SYNCING'

        results.append({
            'sid':         sys_info.get('sid', ''),
            'host':        hostname,
            'site':        site,
            'mode':        mode,
            'status':      status,
            'last_update': now,
        })

    return render_hsr_page(results=results)
