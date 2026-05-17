import configparser
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_config = None


def get_config():
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        _config.read(os.path.join(_BASE_DIR, 'config.ini'))
    return _config


def get_systems():
    raw = get_config().get('systems', 'hosts', fallback='')
    systems = []
    for entry in raw.split(','):
        entry = entry.strip()
        if not entry:
            continue
        parts = [p.strip() for p in entry.split(':')]
        if len(parts) >= 4:
            systems.append({
                'sid':      parts[0],
                'host':     parts[1],
                'instance': parts[2],
                'role':     parts[3],
            })
    return systems


def get_fs_threshold():
    return int(get_config().get('filesystem', 'default_threshold', fallback='80'))


def get_ansible_cfg():
    cfg = get_config()
    base = _BASE_DIR
    return {
        'playbook_dir': os.path.join(base, cfg.get('ansible', 'playbook_dir', fallback='ansible/playbooks')),
        'inventory':    os.path.join(base, cfg.get('ansible', 'inventory',    fallback='ansible/inventory/hosts.ini')),
        'timeout':      int(cfg.get('ansible', 'timeout', fallback='300')),
        'tmp_dir':      cfg.get('paths', 'tmp_dir', fallback='/tmp/sap_mgmt'),
    }
