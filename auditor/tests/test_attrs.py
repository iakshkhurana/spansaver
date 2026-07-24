"""Tests for gen_ai attribute resolution (auditor/llm_auditor/attrs.py).

attrs.py pins the CONFIRMED span keys for this stack (first entry of each list) with older
OpenLLMetry conventions as fallbacks. resolve_usage() must prefer the confirmed key, fall back
when only a legacy key is present, compute total when it's absent, and report which source key
fired — the version-drift safety net. Pure dict logic, no ClickHouse needed.
"""
from __future__ import annotations

import unittest

from auditor.llm_auditor import attrs


class ResolveUsage(unittest.TestCase):
    def test_confirmed_keys_win(self):
        span = {
            "gen_ai.response.model": "gpt-4o-mini-2024-07-18",
            "gen_ai.usage.input_tokens": 54,
            "gen_ai.usage.output_tokens": 11,
            "gen_ai.usage.total_tokens": 65,
            "gen_ai.provider.name": "openai",
        }
        r = attrs.resolve_usage(span)
        self.assertEqual(r["model"], "gpt-4o-mini-2024-07-18")
        self.assertEqual(r["input_tokens"], 54)
        self.assertEqual(r["output_tokens"], 11)
        self.assertEqual(r["total_tokens"], 65)
        self.assertEqual(r["_source_keys"]["input_tokens"], "gen_ai.usage.input_tokens")

    def test_legacy_fallback_keys(self):
        # Only the older Traceloop/OpenLLMetry keys present -> must still resolve.
        span = {
            "llm.request.model": "gpt-4",
            "llm.usage.prompt_tokens": 100,
            "llm.usage.completion_tokens": 20,
        }
        r = attrs.resolve_usage(span)
        self.assertEqual(r["model"], "gpt-4")
        self.assertEqual(r["input_tokens"], 100)
        self.assertEqual(r["output_tokens"], 20)
        self.assertEqual(r["_source_keys"]["output_tokens"], "llm.usage.completion_tokens")

    def test_total_is_computed_when_absent(self):
        span = {
            "gen_ai.response.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 30,
            "gen_ai.usage.output_tokens": 12,
        }
        r = attrs.resolve_usage(span)
        self.assertEqual(r["total_tokens"], 42)
        self.assertEqual(r["_source_keys"]["total_tokens"], "(computed: input+output)")

    def test_missing_core_fields_are_none(self):
        r = attrs.resolve_usage({"unrelated.attr": 1})
        self.assertIsNone(r["model"])
        self.assertIsNone(r["input_tokens"])
        self.assertIsNone(r["output_tokens"])

    def test_pinned_single_keys_are_the_confirmed_ones(self):
        # The detectors read one exact Map cell; these must be the confirmed (first) keys.
        self.assertEqual(attrs.INPUT_TOKEN_KEY, "gen_ai.usage.input_tokens")
        self.assertEqual(attrs.OUTPUT_TOKEN_KEY, "gen_ai.usage.output_tokens")
        self.assertEqual(attrs.MODEL_KEY, "gen_ai.response.model")
        self.assertEqual(attrs.PROMPT_KEY, "gen_ai.input.messages")


if __name__ == "__main__":
    unittest.main()
