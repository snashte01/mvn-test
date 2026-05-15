from __future__ import annotations
import logging
import time
from core.ssh import SSHClient

logger = logging.getLogger(__name__)

WAIT_INTERVAL = 10
WAIT_TIMEOUT = 300


def disable_resource(client: SSHClient, resource: str, dry_run: bool = False) -> str:
    cmd = f"pcs resource disable {resource}"
    if dry_run:
        return f"[DRY-RUN] {cmd}"
    result = client.sudo(cmd)
    if not result.ok:
        raise RuntimeError(f"pcs disable {resource} failed: {result.stderr}")
    _wait_for_stopped(client, resource)
    return f"Disabled pacemaker resource: {resource}"


def enable_resource(client: SSHClient, resource: str, dry_run: bool = False) -> str:
    cmd = f"pcs resource enable {resource}"
    if dry_run:
        return f"[DRY-RUN] {cmd}"
    result = client.sudo(cmd)
    if not result.ok:
        raise RuntimeError(f"pcs enable {resource} failed: {result.stderr}")
    _wait_for_started(client, resource)
    return f"Enabled pacemaker resource: {resource}"


def check_cluster_health(client: SSHClient, dry_run: bool = False) -> str:
    if dry_run:
        return "[DRY-RUN] pcs status --full"
    result = client.sudo("pcs status --full")
    if "FAILED" in result.stdout:
        failed = [line for line in result.stdout.splitlines() if "FAILED" in line]
        raise RuntimeError(f"Cluster has FAILED resources:\n" + "\n".join(failed))
    return "Cluster health OK"


def _wait_for_stopped(client: SSHClient, resource: str):
    elapsed = 0
    while elapsed < WAIT_TIMEOUT:
        result = client.sudo(f"pcs resource show {resource}")
        if "Stopped" in result.stdout or "inactive" in result.stdout.lower():
            logger.debug("Resource %s is stopped", resource)
            return
        time.sleep(WAIT_INTERVAL)
        elapsed += WAIT_INTERVAL
    raise TimeoutError(f"Timed out waiting for {resource} to stop")


def _wait_for_started(client: SSHClient, resource: str):
    elapsed = 0
    while elapsed < WAIT_TIMEOUT:
        result = client.sudo(f"pcs resource show {resource}")
        if "Started" in result.stdout:
            logger.debug("Resource %s is started", resource)
            return
        time.sleep(WAIT_INTERVAL)
        elapsed += WAIT_INTERVAL
    raise TimeoutError(f"Timed out waiting for {resource} to start")
