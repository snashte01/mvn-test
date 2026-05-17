import glob
import os

from runner import run_playbook
from config import get_ansible_cfg, get_fs_threshold
from db.audit import log_action
from templates.filesystem import render_fs_page, render_fs_results, render_extend_result


def run_check(params):
    target    = params.get('target',    ['all'])[0].strip() or 'all'
    threshold = params.get('threshold', [str(get_fs_threshold())])[0].strip() or str(get_fs_threshold())

    cfg = get_ansible_cfg()
    tmp = cfg['tmp_dir']
    os.makedirs(tmp, exist_ok=True)

    for f in glob.glob(os.path.join(tmp, 'fs_*.txt')):
        os.remove(f)

    result = run_playbook(
        'check_filesystem.yml',
        extra_vars={'threshold': threshold},
        limit=None if target == 'all' else target,
    )

    log_action('fs_check', target, result.returncode == 0, f'threshold={threshold}')

    if result.returncode != 0:
        return render_fs_page(error=result.stderr or result.stdout,
                              target=target, threshold=int(threshold))

    filesystems = []
    for filepath in sorted(glob.glob(os.path.join(tmp, 'fs_*.txt'))):
        hostname = os.path.basename(filepath)[3:-4]  # strip "fs_" and ".txt"
        with open(filepath) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) < 6:
                    continue
                filesystems.append({
                    'host':    hostname,
                    'device':  parts[0],
                    'size':    parts[1],
                    'used':    parts[2],
                    'avail':   parts[3],
                    'use_pct': int(parts[4]) if parts[4].isdigit() else 0,
                    'mount':   parts[5],
                })

    return render_fs_results(filesystems, target=target, threshold=int(threshold))


def run_extend(params):
    host         = params.get('host',         [''])[0].strip()
    mount_point  = params.get('mount_point',  [''])[0].strip()
    lv_path      = params.get('lv_path',      [''])[0].strip()
    extend_size  = params.get('extend_size',  ['10G'])[0].strip() or '10G'
    fs_type      = params.get('fs_type',      ['xfs'])[0].strip() or 'xfs'

    if not all([host, mount_point, lv_path]):
        return render_fs_page(error='Missing required parameters: host, mount_point, lv_path')

    cfg = get_ansible_cfg()
    tmp = cfg['tmp_dir']
    os.makedirs(tmp, exist_ok=True)

    result_file = os.path.join(tmp, f'extend_result_{host}.txt')
    if os.path.exists(result_file):
        os.remove(result_file)

    result = run_playbook(
        'extend_lvm.yml',
        extra_vars={
            'target_host': host,
            'lv_path':     lv_path,
            'mount_point': mount_point,
            'extend_size': extend_size,
            'fs_type':     fs_type,
        },
    )

    log_action('fs_extend', host, result.returncode == 0,
               f'lv={lv_path} mount={mount_point} size=+{extend_size}')

    new_size = ''
    if os.path.exists(result_file):
        with open(result_file) as fh:
            new_size = fh.read().strip()

    return render_extend_result(
        success=result.returncode == 0,
        host=host,
        lv_path=lv_path,
        mount_point=mount_point,
        extend_size=extend_size,
        new_size=new_size,
        error=result.stderr or result.stdout,
    )
