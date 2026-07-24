"""Tests for the $ math (auditor/telemetry_auditor/money.py).

Golden rule #2: measured volume x an assumed rate, extrapolated to 30 days, with the math shown.
These tests assert the *relationships* (extrapolation factor, per-GB / per-Mtok arithmetic) and
read the actual rates from `settings`, so they stay green whatever PRICE_* is in .env — we test
that money.py applies the configured rate correctly, not that a specific dollar figure is hit.
"""
from __future__ import annotations

import unittest

from auditor.config import settings
from auditor.telemetry_auditor import money


class PerMonthFactor(unittest.TestCase):
    def test_24h_window_is_30x(self):
        # A full day measured -> a 30-day month.
        self.assertAlmostEqual(money._per_month_factor(24), 30.0)

    def test_half_day_window_is_60x(self):
        self.assertAlmostEqual(money._per_month_factor(12), 60.0)

    def test_zero_or_negative_window_is_zero(self):
        # Guard against divide-by-zero; a non-positive window projects nothing.
        self.assertEqual(money._per_month_factor(0), 0.0)
        self.assertEqual(money._per_month_factor(-5), 0.0)


class IngestMonthly(unittest.TestCase):
    def test_bytes_to_gb_and_rate(self):
        m = money.ingest_monthly(500_000_000, window_hours=24)  # 0.5 GB in the window
        self.assertEqual(m["gb_window"], 0.5)
        self.assertAlmostEqual(m["extrapolation_factor"], 30.0)
        self.assertAlmostEqual(m["gb_month"], 15.0, places=3)
        self.assertEqual(m["rate"], settings.price_per_gb_ingest)
        self.assertEqual(m["cost_month"], round(15.0 * settings.price_per_gb_ingest, 2))
        self.assertEqual(m["basis"], f"{money.BYTES_PER_GB:,} bytes = 1 GB")

    def test_labeled_assumed_rate(self):
        m = money.ingest_monthly(1_000, window_hours=24)
        self.assertIn("assumed", m["rate_unit"])


class TokensMonthly(unittest.TestCase):
    def test_input_output_priced_separately(self):
        in_tok, out_tok, wh = 1_000.0, 200.0, 24
        m = money.tokens_monthly(in_tok, out_tok, window_hours=wh)
        factor = (24.0 / wh) * money.DAYS_PER_MONTH
        self.assertEqual(m["input_tokens_month"], round(in_tok * factor))
        self.assertEqual(m["output_tokens_month"], round(out_tok * factor))
        cost_in = (in_tok * factor / money.TOKENS_PER_MTOK) * settings.price_in_per_mtok
        cost_out = (out_tok * factor / money.TOKENS_PER_MTOK) * settings.price_out_per_mtok
        self.assertEqual(m["cost_month"], round(cost_in + cost_out, 2))
        self.assertEqual(m["rate_in"], settings.price_in_per_mtok)
        self.assertEqual(m["rate_out"], settings.price_out_per_mtok)

    def test_zero_tokens_zero_cost(self):
        m = money.tokens_monthly(0, 0, window_hours=24)
        self.assertEqual(m["cost_month"], 0.0)


class PerMillionMonthly(unittest.TestCase):
    def test_samples_and_spans_use_configured_rates(self):
        s = money.samples_monthly(1_000_000, window_hours=24)   # 1M datapoints/day
        self.assertAlmostEqual(s["extrapolation_factor"], 30.0)
        self.assertEqual(s["count_month"], 30_000_000)
        self.assertEqual(s["rate"], settings.price_per_million_samples)
        self.assertEqual(s["cost_month"], round(30.0 * settings.price_per_million_samples, 2))

        sp = money.spans_monthly(1_000_000, window_hours=24)
        self.assertEqual(sp["rate"], settings.price_per_million_spans)
        self.assertIn("assumed", sp["rate_unit"])


if __name__ == "__main__":
    unittest.main()
