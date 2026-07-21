"""The Finding model + lifecycle — the unit every detector emits and the UI/SSE renders.

Lifecycle (LEAK-CATALOG "Finding lifecycle"): detected → fix_ready → applied → verified, or
→ failed with a loud reason. A Finding is only honest if it carries: measured numbers (real
query output), the $ math (money.py, shows its work), at least one evidence handle (a SigNoz
deep-link AND the raw ClickHouse query), and — for a drop-type fix — a safety proof. Detectors
build these; fixgen fills patch_path; the verifier fills before/after.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Status(str, Enum):
    DETECTED = "detected"
    FIX_READY = "fix_ready"
    APPLIED = "applied"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class Evidence:
    """One piece of proof. `deeplink` opens SigNoz; `raw_query` is the exact CH query run."""

    label: str
    deeplink: str = ""
    filter: str = ""
    raw_query: str = ""


@dataclass
class Finding:
    id: str                       # catalog id, e.g. "T1"
    domain: str                   # "telemetry" | "llm"
    title: str
    summary: str = ""
    service: str = ""             # affected service where applicable
    status: Status = Status.DETECTED

    measured: dict = field(default_factory=dict)   # raw numbers from the detection query
    money: dict = field(default_factory=dict)      # money.py output (shows the math)
    evidence: list = field(default_factory=list)   # list[Evidence]
    safety: dict = field(default_factory=dict)     # {proof: str, references: [...], safe: bool}

    patch_path: str = ""          # set by fixgen (collector/patches/*.yaml)
    verification: dict = field(default_factory=dict)  # before/after, set by verifier
    error: str = ""               # populated iff status == FAILED

    def add_evidence(self, ev: Evidence) -> "Finding":
        self.evidence.append(ev)
        return self

    @property
    def cost_month(self) -> float:
        return float(self.money.get("cost_month", 0.0))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d
