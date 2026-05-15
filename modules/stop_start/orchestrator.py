from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional
from core.inventory import SAPSystem
from core.ssh import SSHClient
from modules.stop_start import pacemaker, sap_control, hana_ops

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    step: str
    status: str  # "ok" | "error" | "dry-run"
    message: str


@dataclass
class JobResult:
    sid: str
    action: str  # "stop" | "start"
    dry_run: bool
    steps: list[StepResult] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


def _ssh(system: SAPSystem, host: str) -> SSHClient:
    return SSHClient(
        host=host,
        user=system.ssh.user,
        key_file=system.ssh.key_file,
        port=system.ssh.port,
    )


def stop(system: SAPSystem, dry_run: bool = False) -> JobResult:
    result = JobResult(sid=system.sid, action="stop", dry_run=dry_run)

    try:
        # Pre-flight cluster check
        if system.pacemaker_enabled and system.pacemaker:
            with _ssh(system, system.pacemaker.cluster_host) as client:
                msg = pacemaker.check_cluster_health(client, dry_run)
                result.steps.append(StepResult("preflight_cluster_check", _status(dry_run), msg))

        # Disable SAP pacemaker resource
        if system.pacemaker_enabled and system.pacemaker:
            with _ssh(system, system.pacemaker.cluster_host) as client:
                msg = pacemaker.disable_resource(client, system.pacemaker.sap_resource, dry_run)
                result.steps.append(StepResult("pcs_disable_sap", _status(dry_run), msg))

        # Stop each app instance
        for instance in system.app_instances:
            with _ssh(system, instance.host) as client:
                msg = sap_control.stop_system(client, instance.instance_number, dry_run)
                result.steps.append(StepResult(f"sapcontrol_stop_{instance.host}", _status(dry_run), msg))

        # Disable HANA pacemaker resource
        if system.pacemaker_enabled and system.pacemaker:
            with _ssh(system, system.pacemaker.cluster_host) as client:
                msg = pacemaker.disable_resource(client, system.pacemaker.hana_resource, dry_run)
                result.steps.append(StepResult("pcs_disable_hana", _status(dry_run), msg))

        # Stop HANA on primary (and secondary if HSR)
        hana = system.hana
        with _ssh(system, hana.primary_host) as client:
            msg = hana_ops.stop_hana(client, hana.sid, hana.instance_number, dry_run)
            result.steps.append(StepResult("hana_stop_primary", _status(dry_run), msg))

        if hana.hsr_enabled and hana.secondary_host:
            with _ssh(system, hana.secondary_host) as client:
                msg = hana_ops.stop_hana(client, hana.sid, hana.instance_number, dry_run)
                result.steps.append(StepResult("hana_stop_secondary", _status(dry_run), msg))

    except Exception as exc:
        logger.exception("Stop failed for %s", system.sid)
        result.error = str(exc)

    return result


def start(system: SAPSystem, dry_run: bool = False) -> JobResult:
    result = JobResult(sid=system.sid, action="start", dry_run=dry_run)

    try:
        # Pre-flight cluster check
        if system.pacemaker_enabled and system.pacemaker:
            with _ssh(system, system.pacemaker.cluster_host) as client:
                msg = pacemaker.check_cluster_health(client, dry_run)
                result.steps.append(StepResult("preflight_cluster_check", _status(dry_run), msg))

        # Start HANA on secondary first (HSR), then primary
        hana = system.hana
        if hana.hsr_enabled and hana.secondary_host:
            with _ssh(system, hana.secondary_host) as client:
                msg = hana_ops.start_hana(client, hana.sid, hana.instance_number, dry_run)
                result.steps.append(StepResult("hana_start_secondary", _status(dry_run), msg))

        with _ssh(system, hana.primary_host) as client:
            msg = hana_ops.start_hana(client, hana.sid, hana.instance_number, dry_run)
            result.steps.append(StepResult("hana_start_primary", _status(dry_run), msg))

        # Enable HANA pacemaker resource
        if system.pacemaker_enabled and system.pacemaker:
            with _ssh(system, system.pacemaker.cluster_host) as client:
                msg = pacemaker.enable_resource(client, system.pacemaker.hana_resource, dry_run)
                result.steps.append(StepResult("pcs_enable_hana", _status(dry_run), msg))

        # Start each app instance
        for instance in system.app_instances:
            with _ssh(system, instance.host) as client:
                msg = sap_control.start_system(client, instance.instance_number, dry_run)
                result.steps.append(StepResult(f"sapcontrol_start_{instance.host}", _status(dry_run), msg))

        # Enable SAP pacemaker resource
        if system.pacemaker_enabled and system.pacemaker:
            with _ssh(system, system.pacemaker.cluster_host) as client:
                msg = pacemaker.enable_resource(client, system.pacemaker.sap_resource, dry_run)
                result.steps.append(StepResult("pcs_enable_sap", _status(dry_run), msg))

    except Exception as exc:
        logger.exception("Start failed for %s", system.sid)
        result.error = str(exc)

    return result


def _status(dry_run: bool) -> str:
    return "dry-run" if dry_run else "ok"
