from __future__ import annotations
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from core.inventory import load_inventory, get_system
from modules.stop_start.orchestrator import stop, start, JobResult

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ZeroOps API",
    description="SAP Basis automation — stop/start, filesystem cleanup, cert checks",
    version="1.0.0",
)


class ActionRequest(BaseModel):
    dry_run: bool = False


class StepOut(BaseModel):
    step: str
    status: str
    message: str


class JobOut(BaseModel):
    sid: str
    action: str
    dry_run: bool
    success: bool
    error: Optional[str]
    steps: list[StepOut]


class SystemOut(BaseModel):
    sid: str
    description: str
    pacemaker_enabled: bool
    app_hosts: list[str]
    hana_primary: str
    hana_secondary: Optional[str]
    hsr_enabled: bool


def _job_to_out(result: JobResult) -> JobOut:
    return JobOut(
        sid=result.sid,
        action=result.action,
        dry_run=result.dry_run,
        success=result.success,
        error=result.error,
        steps=[StepOut(step=s.step, status=s.status, message=s.message) for s in result.steps],
    )


@app.get("/systems", response_model=list[SystemOut], tags=["inventory"])
def list_systems():
    """Return all SAP systems in the inventory."""
    systems = load_inventory()
    return [
        SystemOut(
            sid=s.sid,
            description=s.description,
            pacemaker_enabled=s.pacemaker_enabled,
            app_hosts=[i.host for i in s.app_instances],
            hana_primary=s.hana.primary_host,
            hana_secondary=s.hana.secondary_host,
            hsr_enabled=s.hana.hsr_enabled,
        )
        for s in systems
    ]


@app.get("/systems/{sid}", response_model=SystemOut, tags=["inventory"])
def get_system_info(sid: str):
    """Return details for a single SAP system."""
    try:
        s = get_system(sid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return SystemOut(
        sid=s.sid,
        description=s.description,
        pacemaker_enabled=s.pacemaker_enabled,
        app_hosts=[i.host for i in s.app_instances],
        hana_primary=s.hana.primary_host,
        hana_secondary=s.hana.secondary_host,
        hsr_enabled=s.hana.hsr_enabled,
    )


@app.post("/systems/{sid}/stop", response_model=JobOut, tags=["operations"])
def stop_system(sid: str, req: ActionRequest):
    """Stop a SAP system. Pass dry_run=true to preview steps only."""
    try:
        system = get_system(sid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result = stop(system, dry_run=req.dry_run)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return _job_to_out(result)


@app.post("/systems/{sid}/start", response_model=JobOut, tags=["operations"])
def start_system(sid: str, req: ActionRequest):
    """Start a SAP system. Pass dry_run=true to preview steps only."""
    try:
        system = get_system(sid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result = start(system, dry_run=req.dry_run)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return _job_to_out(result)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
