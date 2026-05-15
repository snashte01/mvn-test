from __future__ import annotations
from worker.celery_app import celery
from core.inventory import get_system
from modules.stop_start.orchestrator import stop, start


@celery.task(bind=True, name="zeroops.stop_system")
def stop_system_task(self, sid: str, dry_run: bool = False) -> dict:
    self.update_state(state="PROGRESS", meta={"step": "starting"})
    system = get_system(sid)
    result = stop(system, dry_run=dry_run)
    return {
        "sid": result.sid,
        "action": result.action,
        "success": result.success,
        "error": result.error,
        "steps": [{"step": s.step, "status": s.status, "message": s.message} for s in result.steps],
    }


@celery.task(bind=True, name="zeroops.start_system")
def start_system_task(self, sid: str, dry_run: bool = False) -> dict:
    self.update_state(state="PROGRESS", meta={"step": "starting"})
    system = get_system(sid)
    result = start(system, dry_run=dry_run)
    return {
        "sid": result.sid,
        "action": result.action,
        "success": result.success,
        "error": result.error,
        "steps": [{"step": s.step, "status": s.status, "message": s.message} for s in result.steps],
    }
