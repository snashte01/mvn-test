"""Thin wrapper around ansible-playbook subprocess calls."""
import subprocess
import tempfile
import json
import os
from config import get_ansible_cfg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_playbook(playbook, extra_vars=None, secure_vars=None, limit=None):
    """Run an Ansible playbook and return the CompletedProcess result.

    extra_vars: dict of non-sensitive vars (added as -e key=value)
    secure_vars: dict of sensitive vars merged into the become-password JSON
                 temp file — never appear in ps aux
    """
    cfg = get_ansible_cfg()

    cmd = [
        'ansible-playbook',
        os.path.join(cfg['playbook_dir'], playbook),
        '-i', cfg['inventory'],
    ]

    if cfg.get('remote_user'):
        cmd += ['-u', cfg['remote_user']]

    if limit:
        cmd += ['--limit', limit]

    if extra_vars:
        for k, v in extra_vars.items():
            cmd += ['-e', f'{k}={v}']

    # Merge become_password and any caller-supplied secure_vars into one JSON
    # temp file so they never appear in ps aux.
    all_secure = {}
    if cfg.get('become_password'):
        all_secure['ansible_become_password'] = cfg['become_password']
    if secure_vars:
        all_secure.update(secure_vars)

    tmp_pass = None
    if all_secure:
        tmp_pass = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', prefix='/tmp/.ap_', delete=False)
        os.chmod(tmp_pass.name, 0o600)
        tmp_pass.write(json.dumps(all_secure))
        tmp_pass.close()
        cmd += ['--extra-vars', f'@{tmp_pass.name}']

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cfg['timeout'],
            cwd=BASE_DIR,
        )
    finally:
        if tmp_pass and os.path.exists(tmp_pass.name):
            os.unlink(tmp_pass.name)
