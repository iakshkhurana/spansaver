"""SpanSaver auditor API — the brain the UI and `make audit/apply/verify` talk to.

Lifecycle over HTTP (LEAK-CATALOG): POST /audit runs the detectors and has fixgen write a
validated patch per finding (detected -> fix_ready). POST /apply/{id} restarts the collector so
the patch takes effect. POST /verify/{id} re-measures + integrity-checks. POST /unapply/{id}
reverses it. Findings from the last audit are held in memory keyed by id so apply/verify can
look them up. Everything fails loud with an actionable message (golden rule #7).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from auditor.config import settings
from auditor.fixgen.generate import generate_patch
from auditor.telemetry_auditor import collector_ctl
from auditor.telemetry_auditor.clickhouse import ClickHouse, ClickHouseUnavailable
from auditor.telemetry_auditor.detectors import run as run_detectors
from auditor.telemetry_auditor.findings import Finding, Status
from auditor.telemetry_auditor.signoz_api import SigNozAPI, SigNozAPIError
from auditor.verifier.verify import verify as verify_finding

app = FastAPI(title="SpanSaver auditor", version="0.2.0")

# Last audit's findings, keyed by id (e.g. "T1"). In-memory is fine for the demo.
_FINDINGS: dict[str, Finding] = {}


@app.get("/health")
def health() -> dict:
    ch_ok, ch_err = True, ""
    try:
        ClickHouse().ping()
    except ClickHouseUnavailable as e:
        ch_ok, ch_err = False, str(e)
    api_ok, api_err = True, ""
    try:
        api_ok = SigNozAPI().ping_auth()
        if not api_ok:
            api_err = "SIGNOZ_API_KEY missing or rejected"
    except SigNozAPIError as e:
        api_ok, api_err = False, str(e)
    status = "ok" if (ch_ok and api_ok) else "degraded"
    return {"status": status,
            "clickhouse": {"ok": ch_ok, "error": ch_err},
            "signoz_api": {"ok": api_ok, "error": api_err},
            "applied_patches": collector_ctl.list_applied()}


@app.post("/audit")
def audit() -> dict:
    """Run telemetry detectors, generate a patch per finding, return the findings."""
    try:
        findings = run_detectors()
    except ClickHouseUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    _FINDINGS.clear()
    out = []
    for f in findings:
        try:
            generate_patch(f)  # detected -> fix_ready, writes collector/patches/<id>.yaml
        except Exception as e:  # noqa: BLE001 - a patch failure shouldn't drop the finding
            f.status = Status.DETECTED
            f.error = f"fixgen failed: {e}"
        _FINDINGS[f.id] = f
        out.append(f.to_dict())
    return {"count": len(out), "findings": out}


def _get(finding_id: str) -> Finding:
    f = _FINDINGS.get(finding_id.upper())
    if f is None:
        raise HTTPException(status_code=404,
                            detail=f"{finding_id} not found — run POST /audit first")
    return f


@app.post("/apply/{finding_id}")
def apply(finding_id: str) -> dict:
    f = _get(finding_id)
    try:
        result = collector_ctl.apply(f.id)
    except collector_ctl.CollectorControlError as e:
        raise HTTPException(status_code=502, detail=str(e))
    f.status = Status.APPLIED
    return {"status": f.status.value, **result}


@app.post("/unapply/{finding_id}")
def unapply(finding_id: str) -> dict:
    fid = finding_id.upper()
    try:
        result = collector_ctl.unapply(fid)
    except collector_ctl.CollectorControlError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if fid in _FINDINGS:
        _FINDINGS[fid].status = Status.FIX_READY
    return {"status": "unapplied", **result}


@app.post("/verify/{finding_id}")
def verify(finding_id: str) -> dict:
    f = _get(finding_id)
    try:
        result = verify_finding(f)
    except ClickHouseUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    if f.status == Status.APPLIED:
        f.status = Status.VERIFIED
    return {"status": f.status.value, "verification": result}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.auditor_port)
