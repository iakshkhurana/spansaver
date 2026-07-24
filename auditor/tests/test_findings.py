"""Tests for the Finding model (auditor/telemetry_auditor/findings.py).

Finding is the unit every detector emits and the UI/SSE renders, so its serialization contract
matters: to_dict() must emit `status` as the string the UI's Status union expects, cost_month must
read from the money dict, and add_evidence must accumulate. Pure dataclass logic.
"""
from __future__ import annotations

import unittest

from auditor.telemetry_auditor.findings import Evidence, Finding, Status


class FindingModel(unittest.TestCase):
    def test_to_dict_serializes_status_as_string(self):
        f = Finding(id="T1", domain="telemetry", title="Debug-log flood")
        d = f.to_dict()
        self.assertEqual(d["status"], "detected")
        self.assertIsInstance(d["status"], str)

    def test_status_values_match_ui_union(self):
        # ui/lib/types.ts Status = 'detected'|'fix_ready'|'applied'|'verified'|'failed'
        self.assertEqual(
            {s.value for s in Status},
            {"detected", "fix_ready", "applied", "verified", "failed"},
        )

    def test_cost_month_reads_money_dict(self):
        f = Finding(id="L1", domain="llm", title="Cacheable duplicates", money={"cost_month": 9.85})
        self.assertEqual(f.cost_month, 9.85)

    def test_cost_month_defaults_to_zero(self):
        f = Finding(id="X", domain="telemetry", title="x")
        self.assertEqual(f.cost_month, 0.0)

    def test_add_evidence_accumulates_and_chains(self):
        f = Finding(id="T3", domain="telemetry", title="Health spam")
        ret = f.add_evidence(Evidence(label="a")).add_evidence(Evidence(label="b"))
        self.assertIs(ret, f)                 # chainable
        self.assertEqual(len(f.evidence), 2)
        self.assertEqual(f.to_dict()["evidence"][0]["label"], "a")

    def test_recommendation_fix_shape(self):
        # L3/L4 recommend-only findings carry a fix dict but stay 'detected'.
        f = Finding(id="L3", domain="llm", title="Retry storms",
                    fix={"kind": "recommendation", "apply": "suggested, not auto-applied"})
        d = f.to_dict()
        self.assertEqual(d["status"], "detected")
        self.assertEqual(d["fix"]["kind"], "recommendation")


if __name__ == "__main__":
    unittest.main()
