"""Tests for the L4 model-tier classifier (auditor/llm_auditor/detectors._is_expensive_model).

The trap this guards: "gpt-4o" is a substring of "gpt-4o-mini", so a naive match would flag the
cheap model as overkill. Cheap markers (mini/haiku/flash/...) must always win. Importing detectors
pulls in the ClickHouse driver, which only ships in the auditor image — so this test self-skips
when run on a host without it, and runs for real inside `make test` in the container.
"""
from __future__ import annotations

import unittest

try:
    from auditor.llm_auditor.detectors import _is_expensive_model
except Exception:  # noqa: BLE001 - clickhouse_driver absent on the host; skip below
    _is_expensive_model = None


@unittest.skipIf(_is_expensive_model is None, "clickhouse_driver not installed (auditor-image only)")
class ExpensiveModel(unittest.TestCase):
    def test_flagship_models_are_expensive(self):
        for m in ("gpt-4o-2024-08-06", "gpt-4-turbo", "claude-opus-4-8",
                  "claude-3-5-sonnet-20241022", "o1", "gemini-1.5-pro"):
            self.assertTrue(_is_expensive_model(m), m)

    def test_cheap_markers_always_win(self):
        for m in ("gpt-4o-mini-2024-07-18", "gpt-4o-mini", "claude-3-5-haiku",
                  "gemini-1.5-flash", "some-8b-model"):
            self.assertFalse(_is_expensive_model(m), m)

    def test_empty_or_unknown_is_not_expensive(self):
        self.assertFalse(_is_expensive_model(""))
        self.assertFalse(_is_expensive_model("gpt-3.5-turbo"))


if __name__ == "__main__":
    unittest.main()
