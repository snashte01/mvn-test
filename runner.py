"""Thin wrapper around ansible-playbook subprocess calls."""

import subprocess
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

    if limit:
        cmd += ['--limit', limit]

    if extra_vars:
        for k, v in extra_vars.items():
            cmd += ['-e', f'{k}={v}']

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=cfg['timeout'],
        cwd=BASE_DIR,
    )
