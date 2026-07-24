"""Tests for metric-name helpers (auditor/telemetry_auditor/schema.py).

These guard the T2 orphan-metric detector against two classic false positives: histogram
component suffixes (.bucket/.count/.sum...) fragmenting one metric into several names, and
infra/runtime plumbing (signoz_*, system_*, http.*, `up`) being mistaken for user metrics.
OTel dotted names and SigNoz underscored names must both normalize the same way.
"""
from __future__ import annotations

import unittest

from auditor.telemetry_auditor import schema


class MetricBaseName(unittest.TestCase):
    def test_strips_histogram_suffixes(self):
        for suf in (".bucket", ".count", ".sum", ".min", ".max"):
            self.assertEqual(schema.metric_base_name(f"checkout_latency{suf}"), "checkout_latency")

    def test_leaves_plain_names_untouched(self):
        self.assertEqual(schema.metric_base_name("orders_total"), "orders_total")

    def test_only_trailing_suffix_stripped(self):
        # ".count" mid-name is not a component suffix.
        self.assertEqual(schema.metric_base_name("a.count.value"), "a.count.value")


class IsInternalMetric(unittest.TestCase):
    def test_signoz_and_collector_internal(self):
        self.assertTrue(schema.is_internal_metric("signoz_calls_total"))
        self.assertTrue(schema.is_internal_metric("otelcol_process_uptime"))

    def test_runtime_and_system(self):
        self.assertTrue(schema.is_internal_metric("system_cpu_time"))
        self.assertTrue(schema.is_internal_metric("process_runtime_memory"))

    def test_dotted_and_underscored_normalize_the_same(self):
        # OTel emits dotted; SigNoz may keep dots. Both must be caught as http_* runtime plumbing.
        self.assertTrue(schema.is_internal_metric("http.server.duration"))
        self.assertTrue(schema.is_internal_metric("http_server_duration"))

    def test_exact_meta_metrics(self):
        self.assertTrue(schema.is_internal_metric("up"))
        self.assertTrue(schema.is_internal_metric("target_info"))

    def test_histogram_component_of_internal_is_internal(self):
        self.assertTrue(schema.is_internal_metric("http.server.duration.bucket"))

    def test_real_user_metrics_are_not_internal(self):
        for name in ("checkout_latency_ms", "orders_created_total", "payment_amount_usd"):
            self.assertFalse(schema.is_internal_metric(name), name)


if __name__ == "__main__":
    unittest.main()
