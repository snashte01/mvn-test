from __future__ import annotations
import logging
import time
from core.ssh import SSHClient

logger = logging.getLogger(__name__)

WAIT_INTERVAL = 10
WAIT_TIMEOUT = 300
GRACEFUL_STOP_TIMEOUT = 180


def stop_hana(client: SSHClient, hana_sid: str, instance_number: str, dry_run: bool = False) -> str:
    hana_user = f"{hana_sid.lower()}adm"
    cmd = f"su - {hana_user} -c 'HDB stop'"
    if dry_run:
        return f"[DRY-RUN] sudo {cmd}"

    result = client.sudo(cmd, timeout=GRACEFUL_STOP_TIMEOUT + 30)
    if not result.ok:
        logger.warning("HDB stop failed, attempting HDB kill-9")
        kill_result = client.sudo(f"su - {hana_user} -c 'HDB kill-9'")
        if not kill_result.ok:
            raise RuntimeError(f"HDB kill-9 also failed: {kill_result.stderr}")
        return f"HANA {hana_sid} force-killed on {client.host}"

    _wait_for_hana_stopped(client, hana_sid, hana_user)
    return f"HANA {hana_sid} stopped on {client.host}"


def start_hana(client: SSHClient, hana_sid: str, instance_number: str, dry_run: bool = False) -> str:
    hana_user = f"{hana_sid.lower()}adm"
    cmd = f"su - {hana_user} -c 'HDB start'"
    if dry_run:
        return f"[DRY-RUN] sudo {cmd}"

    result = client.sudo(cmd, timeout=WAIT_TIMEOUT + 30)
    if not result.ok:
        raise RuntimeError(f"HDB start failed: {result.stderr}")

    _wait_for_hana_started(client, hana_sid, hana_user)
    return f"HANA {hana_sid} started on {client.host}"


def get_hsr_state(client: SSHClient, hana_sid: str, dry_run: bool = False) -> str:
    hana_user = f"{hana_sid.lower()}adm"
    cmd = f"su - {hana_user} -c 'hdbnsutil -sr_state'"
    if dry_run:
        return f"[DRY-RUN] sudo {cmd}"
    result = client.sudo(cmd)
    return result.stdout


def _wait_for_hana_stopped(client: SSHClient, hana_sid: str, hana_user: str):
    elapsed = 0
    while elapsed < WAIT_TIMEOUT:
        result = client.sudo(f"su - {hana_user} -c 'HDB info'")
        if result.exit_code != 0 or not result.stdout.strip():
            return
        time.sleep(WAIT_INTERVAL)
        elapsed += WAIT_INTERVAL
    raise TimeoutError(f"Timed out waiting for HANA {hana_sid} to stop")


def _wait_for_hana_started(client: SSHClient, hana_sid: str, hana_user: str):
    elapsed = 0
    while elapsed < WAIT_TIMEOUT:
        result = client.sudo(f"su - {hana_user} -c 'HDB info'")
        if result.ok and "hdbdaemon" in result.stdout.lower():
            return
        time.sleep(WAIT_INTERVAL)
        elapsed += WAIT_INTERVAL
    raise TimeoutError(f"Timed out waiting for HANA {hana_sid} to start")
