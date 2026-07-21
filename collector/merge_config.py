#!/usr/bin/env python3
"""Deep-merge the baseline collector config with every applied patch into merged.yaml.

Single source of merge truth: run at container start by entrypoint.sh, and re-run by the
auditor on apply/unapply. Patches apply in sorted filename order for determinism. The
baseline is never mutated.

Merge semantics:
  dict   -> recurse key by key
  list   -> append patch items not already present (extends pipeline processor lists,
            exporter lists, resource attributes, etc. without duplicating)
  scalar -> patch value wins
"""
import glob
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "otel-collector.baseline.yaml")
PATCH_GLOB = os.path.join(HERE, "patches", "*.yaml")
OUT = os.path.join(HERE, "merged.yaml")


def deep_merge(base, patch):
    if isinstance(base, dict) and isinstance(patch, dict):
        for k, v in patch.items():
            base[k] = deep_merge(base[k], v) if k in base else v
        return base
    if isinstance(base, list) and isinstance(patch, list):
        merged = list(base)
        for item in patch:
            if item not in merged:
                merged.append(item)
        return merged
    return patch


def main():
    with open(BASELINE) as f:
        merged = yaml.safe_load(f) or {}
    patches = sorted(glob.glob(PATCH_GLOB))
    for path in patches:
        with open(path) as f:
            merged = deep_merge(merged, yaml.safe_load(f) or {})
    with open(OUT, "w") as f:
        yaml.safe_dump(merged, f, sort_keys=False)
    names = [os.path.basename(p) for p in patches]
    print(f"merge_config: wrote merged.yaml (baseline + {len(patches)} patch(es): {names})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
