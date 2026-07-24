# PENDING — pick up here

Snapshot as of the last session. Ordered by leverage. Commands are copy-paste ready.
Environment note: stack runs in **WSL** (`/mnt/k/hacks/signoz`); UI runs on host via `make ui`.

---

## ✅ Already done & committed
- **D4**: verify loop (before/after + integrity + green banner), T4 cardinality detector,
  UI black-console redesign + front terminal, `make demo` end-to-end, DEMO-SCRIPT real numbers.
- **D5 core**: README refresh, JUDGING-MAP links, mermaid architecture diagram, repo cleanup
  (dead KPIRow removed, `*.tsbuildinfo` gitignored), SSE→REST doc accuracy.
- **Explainer feature CODE** (auditor's own traced LLM call) — written, compiles, **committed** (0455eb3).
  Still **not yet run live** (needs a key + auditor rebuild — see §1).
- **D5 track reframe (§2/§3) — DONE (code side).** README hook + Why + self-disclosing bullet now
  lead with *AI & Agent Observability / self-healing*; JUDGING-MAP + DEMO-SCRIPT retargeted to the
  track and pointed at `/explain`. Docs only — no numbers invented.
- **UI Explain-with-AI (§5) — DONE.** `api.explainFinding` + `Explanation` type (with mock), an
  Explain panel on `/leak/[id]` (shows the model, tokens, and this-call `cost_usd`), and an
  `explain <id>` command in the front terminal. UI typechecks clean.
- **Integrity-story assets (§4) — files created, import still human.** `dashboards/telemetry-cost.json`
  (confirmed-column T1/T3/T4 panels) + `alerts/README.md` (3 alert-rule recipes). Importing the
  dashboards and creating the alerts in SigNoz is still a live/human step.
- **L3 (retry storms) + L4 (model overkill) detectors — WRITTEN (recommend-only).** Additive,
  confirmed columns/keys only, `run()` hardened so a bad detector can't sink the audit. **Not yet
  run live** (no local ClickHouse; compiles + tier-logic unit-checked). Caveats to know on camera:
  L3 fires only if the stack records gen_ai error spans; L4 returns nothing on the gpt-4o-mini demo
  stack (mini isn't overkill — that's the honest result). Both are recommend-only: no Apply button,
  the UI shows "suggested, not auto-applied".

---

## 0. Commit + push the explainer (git — I do it myself)
```bash
git add auditor/llm_auditor/explainer.py auditor/main.py auditor/telemetry_auditor/findings.py auditor/requirements.txt
git commit -m "feat(auditor): add self-tracing /explain endpoint (real LLM call, OpenAI/Anthropic)"
git push
```
(Leave out `ui/next-env.d.ts`, `.claude/settings.local.json`, `*.tsbuildinfo`.)

---

## 1. Make `/explain` live (proves "audits its own AI cost")  ⭐ highest value
1. `.env` must have: `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...`
2. Rebuild auditor (also picks up the verify `series_now` guard not yet in the running image):
   ```bash
   docker compose up -d --build auditor
   ```
3. Live test:
   ```bash
   curl -s -X POST localhost:8100/audit >/dev/null
   curl -s -X POST localhost:8100/explain/T2 | python3 -m json.tool
   ```
   Expect: real `explanation` + `usage` + `cost_usd`, and a `spansaver-auditor` gen_ai span in SigNoz.
4. **Record the real `cost_usd`** — it fills the DEMO-SCRIPT 2:20 kicker (`<MEASURE ¢>`).

---

## 2. TRACK REFRAME  ⭐ biggest scoring lever  — ✅ DONE (code side)
Track = **"AI & Agent Observability — trace, monitor, debug AI-native systems."** Reframed, not
rebuilt: README hook + Why now lead with the self-healing agent framing (anchored to example build
**#5 "Self-healing infra with SigNoz metrics"**); JUDGING-MAP has a track banner + criteria pointed
at L1/`/explain`; DEMO-SCRIPT 0:00–0:20 names the track. Telemetry-cost demoted to supporting.
Left for you: gut-check the copy reads the way you want on camera.

---

## 3. Docs: point "self-disclosing" claim at `/explain`  — ✅ DONE
README "Audits its own AI cost" bullet, JUDGING-MAP criterion 2/4, and DEMO-SCRIPT 2:20 kicker now
reference `POST /explain/<id>` and its `cost_usd`. The `<MEASURE ¢>` placeholder stays until you run
§1 live and drop in the real figure (kept honest — no invented number).

---

## 4. Never-verified-live gaps (real, not cosmetic)
- **T4 apply→verify end-to-end** — last run gave `series_now=0` because `checkout_latency_ms`
  (the cardinality metric) had stopped emitting. Need it flowing, then:
  ```bash
  make apply F=T4 && sleep 90 && make verify F=T4   # expect window_basis "since apply", down ~100%
  ```
- **Integrity story** — assets now exist: import BOTH `dashboards/agent-ops.json` and
  `dashboards/telemetry-cost.json`, and create the 3 alert rules in `alerts/README.md` (confirmed
  ClickHouse queries, ~30s each in the SigNoz UI). Then the green banner reads "N dashboards / 3
  alerts intact". Importing/creating is the only step left — it's live/human.

---

## 5. UI polish  — ✅ DONE
Explain-with-AI shipped: panel on `/leak/[id]` (explanation + model + tokens + this-call `cost_usd`)
and `explain <id>` in the front terminal. Backed by `api.explainFinding` (mock included, so it demos
without a key). Live path needs §1 (key + auditor rebuild).

---

## 6. Human-only (you)
- Rehearse the 3-min demo 3× · record ALL backup segments (before any code change) ·
  final 3:00 video cut · submit per the hackathon form.

---

## Gotchas / context for tomorrow
- **Auditor code is baked into the image** — after ANY `auditor/*.py` change, run
  `docker compose up -d --build auditor` (a plain restart won't pick it up).
- **ClickHouse dies on WSL** with config-file I/O errors sometimes — recover with
  `docker start signoz-telemetrystore-clickhouse-0-0 signoz-telemetrykeeper-clickhousekeeper-0 signoz-ingester-1`
  (back to healthy in ~5s). Check `docker compose ps -a` if `/health` is empty.
- **UI**: `make ui` (pnpm dev on :3000). If `pnpm dev` fails on ignored build scripts, run
  `cd ui && pnpm approve-builds` once. Don't docker-build `ui` (no Dockerfile; it's `profiles: full`).
- **PowerShell `curl`** is `Invoke-WebRequest` (prompts for Uri). Use `curl.exe` or run in WSL.
- **`make demo`** takes `DEMO_WAIT` (seconds, default 60) for post-apply data to land.
- **Git**: I handle commits/pushes myself — Claude only gives the commands + messages (no co-author line).
