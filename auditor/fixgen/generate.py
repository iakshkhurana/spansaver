"""fixgen — turn a Finding into a collector patch file (golden rule #4: patches are files).

Each patch is a standalone YAML dropped in collector/patches/<ID>.yaml with a header comment
(finding id + generated-at timestamp). It defines a scoped OTel `filter` processor and wires it
into the right pipeline; merge_config.py deep-merges it onto the baseline at collector start /
on apply. We NEVER edit the baseline. Patches are "validated" before being trusted: valid YAML,
the processor is defined, and the pipeline references it (checked by validate_patch()).

Filter semantics: the OTel filterprocessor DROPS any record matching a listed OTTL condition.
So every condition here describes exactly the waste to remove — scoped to the flagged services /
metric names / health routes, and (for traces/logs) never touching error-status records.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import yaml

from auditor.config import settings
from auditor.telemetry_auditor import schema
from auditor.telemetry_auditor.findings import Finding, Status


def _proc_name(fid: str) -> str:
    return f"filter/spansaver_{fid.lower()}"


def _t1_patch(f: Finding) -> dict:
    services = [s["service"] for s in f.measured.get("services", [])] or ([f.service] if f.service else [])
    svc_clause = " or ".join(f'resource.attributes["service.name"] == "{s}"' for s in services)
    # DEBUG/TRACE = severity_number 1..8; leave UNSPECIFIED (0) and >=INFO untouched.
    cond = f'severity_number >= 1 and severity_number < {schema.SEVERITY_INFO_MIN} and ({svc_clause})'
    return {
        "processors": {_proc_name("T1"): {"error_mode": "ignore", "logs": {"log_record": [cond]}}},
        "service": {"pipelines": {"logs": {"processors": [_proc_name("T1")]}}},
    }


def _t2_patch(f: Finding) -> dict:
    names = [o["metric"] for o in f.measured.get("orphans", [])]
    conds = [f'name == "{n}"' for n in names]
    return {
        "processors": {_proc_name("T2"): {"error_mode": "ignore", "metrics": {"metric": conds}}},
        "service": {"pipelines": {"metrics": {"processors": [_proc_name("T2")]}}},
    }


def _t3_patch(f: Finding) -> dict:
    # Match health probe span names; KEEP error-status spans (they are real signal).
    cond = ('IsMatch(name, "(?i).*(healthz|/health|/ready|/live).*") '
            'and status.code != STATUS_CODE_ERROR')
    return {
        "processors": {_proc_name("T3"): {"error_mode": "ignore", "traces": {"span": [cond]}}},
        "service": {"pipelines": {"traces": {"processors": [_proc_name("T3")]}}},
    }


_BUILDERS = {"T1": _t1_patch, "T2": _t2_patch, "T3": _t3_patch}


def _pipeline_key_for(patch: dict) -> str:
    return next(iter(patch["service"]["pipelines"]))


def validate_patch(patch: dict, fid: str) -> None:
    """Structural validation: processor defined, referenced in exactly one pipeline, has conditions."""
    pname = _proc_name(fid)
    procs = patch.get("processors", {})
    if pname not in procs:
        raise ValueError(f"{fid}: patch does not define processor {pname}")
    body = procs[pname]
    signal = next((k for k in ("logs", "metrics", "traces") if k in body), None)
    if signal is None:
        raise ValueError(f"{fid}: processor {pname} has no logs/metrics/traces block")
    conds = next(iter(body[signal].values()))
    if not conds:
        raise ValueError(f"{fid}: processor {pname} has no drop conditions (would be a no-op)")
    pipe = _pipeline_key_for(patch)
    if pname not in patch["service"]["pipelines"][pipe]["processors"]:
        raise ValueError(f"{fid}: {pname} not wired into the {pipe} pipeline")


def generate_patch(finding: Finding) -> str:
    """Build, validate, and write the patch for a finding. Returns the file path and updates the
    finding (patch_path + status=FIX_READY). Raises if the finding id has no generator or the
    patch fails validation — we never write an unvalidated patch."""
    builder = _BUILDERS.get(finding.id)
    if builder is None:
        raise ValueError(f"no patch generator for finding {finding.id}")
    patch = builder(finding)
    validate_patch(patch, finding.id)

    # fixgen writes to the STAGED dir; /apply promotes it into the active patches dir. This is
    # what makes "apply exactly T1" honest — generating a patch never activates it.
    os.makedirs(settings.generated_dir, exist_ok=True)
    path = os.path.join(settings.generated_dir, f"{finding.id}.yaml")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    header = (
        f"# SpanSaver generated patch -- finding {finding.id}: {finding.title}\n"
        f"# generated-at: {ts}\n"
        f"# {finding.summary}\n"
        f"# Deep-merged onto collector/otel-collector.baseline.yaml by merge_config.py. "
        f"Do not edit by hand.\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(patch, fh, sort_keys=False, default_flow_style=False)

    finding.patch_path = path
    finding.status = Status.FIX_READY
    return path


if __name__ == "__main__":
    # Smoke test: build patches from synthetic findings and print them (no ClickHouse needed).
    demo = [
        Finding(id="T1", domain="telemetry", title="Debug-log flood", service="orders",
                summary="orders DEBUG flood", measured={"services": [{"service": "orders"}]}),
        Finding(id="T2", domain="telemetry", title="Orphan metrics",
                summary="6 orphan metrics",
                measured={"orphans": [{"metric": "payments_legacy_retry_total"},
                                       {"metric": "payments_shadow_ledger_writes_total"}]}),
        Finding(id="T3", domain="telemetry", title="Health-check span spam", summary="health spam"),
    ]
    for f in demo:
        p = generate_patch(f)
        print(f"\n=== {p} ===")
        print(open(p, encoding="utf-8").read())
