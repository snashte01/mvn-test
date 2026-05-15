from __future__ import annotations
import logging
import time
from core.ssh import SSHClient

logger = logging.getLogger(__name__)

SAPCONTROL = "/usr/sap/hostctrl/exe/sapcontrol"
WAIT_INTERVAL = 15
WAIT_TIMEOUT = 600


def stop_system(client: SSHClient, instance_number: str, dry_run: bool = False) -> str:
    cmd = f"{SAPCONTROL} -nr {instance_number} -function StopSystem ALL"
    if dry_run:
        return f"[DRY-RUN] sudo {cmd}"
    result = client.sudo(cmd)
    if result.exit_code not in (0, 4):
        raise RuntimeError(f"sapcontrol StopSystem failed: {result.stderr}")
    _wait_for_state(client, instance_number, target_state=4)
    return f"SAP instance {instance_number} stopped on {client.host}"


def start_system(client: SSHClient, instance_number: str, dry_run: bool = False) -> str:
    cmd = f"{SAPCONTROL} -nr {instance_number} -function StartSystem ALL"
    if dry_run:
        return f"[DRY-RUN] sudo {cmd}"
    result = client.sudo(cmd)
    if result.exit_code not in (0, 4):
        raise RuntimeError(f"sapcontrol StartSystem failed: {result.stderr}")
    _wait_for_state(client, instance_number, target_state=3)
    return f"SAP instance {instance_number} started on {client.host}"


def get_process_list(client: SSHClient, instance_number: str) -> str:
    cmd = f"{SAPCONTROL} -nr {instance_number} -function GetProcessList"
    result = client.sudo(cmd)
    return result.stdout


def _wait_for_state(client: SSHClient, instance_number: str, target_state: int):
    """Wait until GetSystemInstanceList reports the desired state.
    State 3 = GREEN (running), State 4 = GRAY (stopped).
    """
    elapsed = 0
    while elapsed < WAIT_TIMEOUT:
        result = client.sudo(
            f"{SAPCONTROL} -nr {instance_number} -function GetSystemInstanceList"
        )
        lines = result.stdout.splitlines()
        states = set()
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                try:
                    states.add(int(parts[6]))
                except ValueError:
                    pass
        if states and all(s == target_state for s in states):
            return
        time.sleep(WAIT_INTERVAL)
        elapsed += WAIT_INTERVAL
    raise TimeoutError(
        f"Timed out waiting for SAP instance {instance_number} to reach state {target_state}"
    )
