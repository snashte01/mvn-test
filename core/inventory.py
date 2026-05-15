from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class SSHConfig:
    user: str
    key_file: str
    port: int = 22


@dataclass
class AppInstance:
    host: str
    instance_number: str


@dataclass
class HanaConfig:
    primary_host: str
    sid: str
    instance_number: str
    hsr_enabled: bool
    secondary_host: Optional[str] = None


@dataclass
class PacemakerConfig:
    sap_resource: str
    hana_resource: str
    cluster_host: str


@dataclass
class SAPSystem:
    sid: str
    description: str
    pacemaker_enabled: bool
    ssh: SSHConfig
    app_instances: list[AppInstance]
    hana: HanaConfig
    pacemaker: Optional[PacemakerConfig] = None


def load_inventory(config_path: str | Path = None) -> list[SAPSystem]:
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "systems.yaml"
    config_path = Path(config_path).expanduser()

    with open(config_path) as f:
        data = yaml.safe_load(f)

    systems = []
    for s in data.get("systems", []):
        ssh = SSHConfig(**s["ssh"])

        app_instances = [AppInstance(**i) for i in s["app_instances"]]

        hana_data = s["hana"]
        hana = HanaConfig(
            primary_host=hana_data["primary_host"],
            secondary_host=hana_data.get("secondary_host"),
            sid=hana_data["sid"],
            instance_number=hana_data["instance_number"],
            hsr_enabled=hana_data["hsr_enabled"],
        )

        pacemaker = None
        if s.get("pacemaker"):
            pacemaker = PacemakerConfig(**s["pacemaker"])

        systems.append(SAPSystem(
            sid=s["sid"],
            description=s["description"],
            pacemaker_enabled=s["pacemaker_enabled"],
            ssh=ssh,
            app_instances=app_instances,
            hana=hana,
            pacemaker=pacemaker,
        ))

    return systems


def get_system(sid: str, config_path: str | Path = None) -> SAPSystem:
    systems = load_inventory(config_path)
    for system in systems:
        if system.sid.upper() == sid.upper():
            return system
    raise ValueError(f"System '{sid}' not found in inventory")
