"""Thin wrapper around ansible-playbook subprocess calls."""
import subprocess
import tempfile
import os
from config import get_ansible_cfg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_playbook(playbook, extra_vars=None, limit=None):
    """Run an Ansible playbook and return the CompletedProcess result."""
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

    # Write become password to a temp file so it never appears in `ps aux`.
    tmp_pass = None
    if cfg.get('become_password'):
        tmp_pass = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yml', prefix='/tmp/.ap_', delete=False)
        os.chmod(tmp_pass.name, 0o600)
        tmp_pass.write(f'ansible_become_password: "{cfg["become_password"]}"\n')
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
