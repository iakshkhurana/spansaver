# Plan — July 21 → 26

Roles: **Human** = environment, keys, judgment calls, recording, socials, submission.
**Claude** = code, configs, dashboards JSON, docs, video script. Daily: one 30-sec progress
clip posted tagging @wemakedevs + SigNoz (Social Buzz side-track = free swag).

## D1 · Mon Jul 21 — Foundations
SigNoz self-hosted and reachable · victim stack emitting all three signals · askdocs LLM
spans confirmed with token attributes (keys pinned) · waste toggles working · SETUP.md
checklist all green · SigNoz MCP wired into the editor.
**DoD:** `make up && make waste-on && make traffic` → three services + junk visible in SigNoz.

## D2 · Tue Jul 22 — Telemetry auditor
ClickHouse introspection + volume queries · SigNoz API routes pinned · detectors T1, T2, T3 ·
$ math · fixgen writes validated patches · manual apply + crude verify via CLI.
**DoD:** `make audit` prints T1–T3 with evidence URLs and a patch file each; applying T1
visibly drops log volume in SigNoz.

## D3 · Wed Jul 23 — LLM auditor + Mission Control v1
Detectors L1, L2 · cache implementation in askdocs · UI: report page + leak detail + SSE
status · evidence deep-links land correctly · Agent Ops dashboard imported.
**DoD:** full loop works for T2 and L1 from the UI (detect → fix_ready → applied), verify
still allowed to be CLI-level.

## D4 · Thu Jul 24 — Verify loop + polish + record   ← feature freeze at EOD
Verifier with before/after windows + dashboard/alert integrity sweep · green banner · T4
detector if time · Judge Mode page · dark theme pass · rehearse demo 3× · record ALL backup
segments · replace placeholder numbers in DEMO-SCRIPT.md with real ones.
**DoD:** `make demo` end-to-end without touching a terminal mid-flow; backup video exists.

## D5 · Fri Jul 25 — Ship
README final (quickstart <15 min) · architecture diagram image · final 3:00 video cut ·
JUDGING-MAP links filled · repo cleaned (no dead code, no mock data on main path) · submit
per the form (check the hackathon page — form was "coming soon") · buffer for the unknown
submission requirements. Sat Jul 26 = margin only, not plan.

## Cut lines (drop in this order when behind)
1. T5, L3, L4 → catalog-only "future work"
2. T4 → mention in video over a static query result
3. Auto-apply for L2 → show the prompt diff, apply manually on camera
4. SSE → polling every 3s
**Never cut:** the T2 safety proof, the verify banner, L1 cache drop, Judge Mode, the video.

## Standing risks
- SigNoz version drift vs docs → budgeted in D1/D2 via introspection-first rule.
- Demo data too thin → traffic generator runs continuously from D1; never wipe volumes.
- Scope temptation → any new idea goes to a `LATER.md`, not into code, after D3.
