"""Usage cross-reference — the engine behind every "referenced by: none" safety proof.

A drop-type fix is only safe if nothing anyone looks at depends on the data being dropped. We
prove that by pulling the REAL dashboards and alert rules from the SigNoz API and searching
their full JSON for the thing we want to drop (a service name, a metric name, a route). The
search is shape-agnostic on purpose: SigNoz's dashboard/alert query JSON nests differently
across versions, so instead of pinning a fragile path we flatten every string in the payload
and look for the needle. That errs toward "referenced" (safe): if a name appears anywhere in
any dashboard or alert, we refuse to call it orphaned. Fail-loud if the API is unreachable —
we must never emit a safety proof we couldn't actually check (golden rule #7).
"""
from __future__ import annotations

from dataclasses import dataclass

from auditor.telemetry_auditor.signoz_api import SigNozAPI, SigNozAPIError


@dataclass
class ReferenceSource:
    kind: str      # "dashboard" | "alert"
    name: str      # human name/title of the dashboard or rule
    text: str      # all string content of that source, lowercased, for substring search


def _collect_strings(node, out: list[str]) -> None:
    """Recursively gather every string (dict keys, list items, scalar values) under `node`."""
    if isinstance(node, dict):
        for k, v in node.items():
            out.append(str(k))
            _collect_strings(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_strings(item, out)
    elif node is not None:
        out.append(str(node))


def _title_of(obj: dict) -> str:
    if not isinstance(obj, dict):
        return "(unnamed)"
    for key in ("title", "name", "alert", "description"):
        v = obj.get(key)
        if isinstance(v, str) and v:
            return v
    # SigNoz dashboards nest the title under "data".
    data = obj.get("data")
    if isinstance(data, dict):
        return _title_of(data)
    return "(unnamed)"


def build_corpus(api: SigNozAPI | None = None) -> list[ReferenceSource]:
    """Fetch dashboards + alert rules and flatten each into a searchable ReferenceSource."""
    api = api or SigNozAPI()
    sources: list[ReferenceSource] = []

    dash = api.dashboards()
    dash_list = dash.get("data", dash) if isinstance(dash, dict) else dash
    for d in dash_list or []:
        strings: list[str] = []
        _collect_strings(d, strings)
        sources.append(ReferenceSource("dashboard", _title_of(d), " ".join(strings).lower()))

    rules = api.alert_rules()
    rules_list = rules.get("data", {}).get("rules", []) if isinstance(rules, dict) else rules
    for r in rules_list or []:
        strings = []
        _collect_strings(r, strings)
        sources.append(ReferenceSource("alert", _title_of(r), " ".join(strings).lower()))

    return sources


def find_references(corpus: list[ReferenceSource], needle: str) -> list[dict]:
    """Return [{kind, name}] for every source whose JSON contains `needle` (case-insensitive)."""
    n = needle.lower()
    return [{"kind": s.kind, "name": s.name} for s in corpus if n and n in s.text]


def safety_for(corpus: list[ReferenceSource], needles: list[str], subject: str) -> dict:
    """Build a Finding.safety dict: is `subject` safe to drop given the reference corpus?

    Safe iff NONE of the needles (e.g. a metric name, or [service, 'debug']) appear in any
    dashboard or alert. Returns the proof text + the actual references found (empty on the
    clean demo instance), so the UI shows the cross-check, not a bare claim.
    """
    refs: list[dict] = []
    for needle in needles:
        refs.extend(find_references(corpus, needle))
    # de-dup by (kind, name)
    seen = set()
    unique = [r for r in refs if (r["kind"], r["name"]) not in seen and not seen.add((r["kind"], r["name"]))]
    safe = len(unique) == 0
    n_dash = sum(1 for s in corpus if s.kind == "dashboard")
    n_alert = sum(1 for s in corpus if s.kind == "alert")
    if safe:
        proof = (
            f"{subject}: referenced by none. Checked all {n_dash} dashboard(s) and "
            f"{n_alert} alert rule(s); 0 reference it."
        )
    else:
        proof = f"{subject}: referenced by {len(unique)} source(s) — NOT safe to drop automatically."
    return {"safe": safe, "proof": proof, "references": unique,
            "checked": {"dashboards": n_dash, "alerts": n_alert}}


def try_build_corpus() -> tuple[list[ReferenceSource], str]:
    """Corpus + an error string ('' on success). Lets detectors run detection even if the API
    is down, marking the safety proof as unverified rather than crashing the whole audit."""
    try:
        return build_corpus(), ""
    except SigNozAPIError as e:
        return [], str(e)
