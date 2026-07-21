"""Apply / unapply a fix patch and reload the collector.

Apply = the patch file already written by fixgen into collector/patches/ takes effect. The OTel
Collector does not hot-reload, so we restart its container; entrypoint.sh re-runs merge_config
(baseline + patches/*.yaml -> merged.yaml) on start, so the restart picks up exactly the patch
set currently on disk. Unapply = delete the patch file, then restart. The baseline is never
touched (golden rule #4). Reversibility is a feature we demo — unapply must always work.

Fail loud (golden rule #7): if the collector container can't be reached/restarted, say so with
the container name and the fix (mount the docker socket / set COLLECTOR_CONTAINER), never
pretend the reload happened.
"""
from __future__ import annotations

import os
import shutil

from auditor.config import settings

COLLECTOR_CONTAINER = os.getenv("COLLECTOR_CONTAINER", "signoz-collector-1")


class CollectorControlError(RuntimeError):
    pass


def patch_path(finding_id: str) -> str:
    """Path in the ACTIVE dir (merged by the collector)."""
    return os.path.join(settings.patches_dir, f"{finding_id}.yaml")


def staged_path(finding_id: str) -> str:
    """Path in the STAGED dir (fixgen output, inert until applied)."""
    return os.path.join(settings.generated_dir, f"{finding_id}.yaml")


def patch_exists(finding_id: str) -> bool:
    return os.path.isfile(patch_path(finding_id))


def staged_exists(finding_id: str) -> bool:
    return os.path.isfile(staged_path(finding_id))


def remove_patch(finding_id: str) -> bool:
    p = patch_path(finding_id)
    if os.path.isfile(p):
        os.remove(p)
        return True
    return False


def list_applied() -> list[str]:
    d = settings.patches_dir
    if not os.path.isdir(d):
        return []
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".yaml"))


def reload_collector() -> dict:
    """Restart the collector container so it re-merges patches. Returns {reloaded, container}."""
    try:
        import docker  # imported lazily so non-apply paths don't require the SDK
    except ImportError as e:  # pragma: no cover
        raise CollectorControlError(
            "python docker SDK not installed — add 'docker' to requirements and rebuild the auditor image."
        ) from e
    try:
        client = docker.from_env()
        container = client.containers.get(COLLECTOR_CONTAINER)
        container.restart(timeout=15)
    except Exception as e:  # noqa: BLE001 - surface any docker error loudly
        raise CollectorControlError(
            f"could not restart collector container '{COLLECTOR_CONTAINER}': {e}. "
            "Mount the docker socket into the auditor and set COLLECTOR_CONTAINER to the "
            "running collector's name (docker ps)."
        ) from e
    return {"reloaded": True, "container": COLLECTOR_CONTAINER}


def apply(finding_id: str) -> dict:
    if not staged_exists(finding_id):
        raise CollectorControlError(
            f"no generated patch for {finding_id} at {staged_path(finding_id)} — run /audit first."
        )
    os.makedirs(settings.patches_dir, exist_ok=True)
    shutil.copyfile(staged_path(finding_id), patch_path(finding_id))  # promote staged -> active
    result = reload_collector()
    return {"applied": finding_id, "patch": patch_path(finding_id), **result}


def unapply(finding_id: str) -> dict:
    removed = remove_patch(finding_id)
    result = reload_collector()
    return {"unapplied": finding_id, "patch_removed": removed, **result}
