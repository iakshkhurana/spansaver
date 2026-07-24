import { Finding, AuditResponse, HealthResponse, ActionResponse, ExplainResponse } from './types'

// Points at the auditor FastAPI brain. Default matches AUDITOR_PORT in .env.example (8100).
const API_BASE = process.env.NEXT_PUBLIC_AUDITOR_URL || 'http://localhost:8100'
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true'

// ── Real-shaped fixtures (design preview only; gated behind NEXT_PUBLIC_USE_MOCK). One LLM
//    finding (config-diff fix) and one telemetry finding (collector-patch fix) so both detail
//    layouts render. Numbers here are illustrative — the real values come from live queries. ──
const mockFindings: Finding[] = [
  {
    id: 'L1',
    domain: 'llm',
    title: 'Cacheable duplicate prompts',
    summary:
      '10 distinct prompts were answered fresh 250 times (240 exact repeats) — every repeat is a cache miss paid in full.',
    service: 'askdocs',
    status: 'fix_ready',
    measured: {
      distinct_prompts: 10,
      total_calls: 250,
      total_repeats: 240,
      wasted_input_tokens_window: 189000,
      wasted_output_tokens_window: 14200,
      window_hours: 24,
      duplicate_prompts: [
        { count: 40, repeats: 39, avg_input_tokens: 800, avg_output_tokens: 60, sample_prompt: "[{'role':'system'...}]" },
        { count: 32, repeats: 31, avg_input_tokens: 780, avg_output_tokens: 55, sample_prompt: "[{'role':'system'...}]" },
      ],
    },
    money: {
      input_tokens_window: 189000, output_tokens_window: 14200, extrapolation_factor: 30.0,
      input_tokens_month: 5670000, output_tokens_month: 426000, window_hours: 24,
      rate_in: 3.0, rate_out: 15.0, rate_unit: '$/Mtok in|out (assumed)', cost_month: 23.4,
    },
    evidence: [{
      label: 'gen_ai spans for askdocs in SigNoz Traces Explorer',
      deeplink: "http://localhost:8080/traces-explorer?relativeTime=1440m&filter=service.name+%3D+%27askdocs%27",
      filter: "service.name = 'askdocs'",
      raw_query: "SELECT cityHash64(attributes_string['gen_ai.input.messages']) AS prompt_hash, count() AS n, avg(attributes_number['gen_ai.usage.input_tokens']) AS avg_in FROM signoz_traces.distributed_signoz_index_v3 WHERE timestamp >= now() - INTERVAL 24 HOUR AND serviceName = 'askdocs' GROUP BY prompt_hash HAVING n >= 5",
    }],
    safety: {
      safe: true,
      proof: 'Fix = exact-match, TTL-bounded response cache. A cached answer is returned only for a byte-identical prompt; no semantic matching, so no wrong-answer risk. Non-repeat traffic is unaffected.',
      references: [],
      checked: { cache_type: 'exact-match sha256(question)', ttl_seconds: 3600 },
    },
    patch_path: '',
    fix: {
      kind: 'config', target: 'askdocs',
      diff: '- WASTE_LLM_NOCACHE=1\n+ WASTE_LLM_NOCACHE=0\n- ASKDOCS_CACHE=0\n+ ASKDOCS_CACHE=1',
      apply: 'restart askdocs with ASKDOCS_CACHE=1 and WASTE_LLM_NOCACHE=0',
      note: 'Exact-match, TTL-bounded cache — reversible by flipping the env back.',
      path: 'collector/generated/L1.diff',
    },
    verification: {},
    error: '',
  },
  {
    id: 'T1',
    domain: 'telemetry',
    title: 'Debug-log flood',
    summary: '1 service ships DEBUG/TRACE logs as >=30% of its log bytes: orders.',
    service: 'orders',
    status: 'fix_ready',
    measured: {
      services: [{ service: 'orders', debug_logs: 48200, total_logs: 61000, debug_bytes: 49200000, total_bytes: 63000000, debug_share: 0.781 }],
      total_debug_bytes_window: 49200000, window_hours: 24,
    },
    money: {
      bytes_window: 49200000, gb_window: 0.0492, window_hours: 24, extrapolation_factor: 30.0,
      gb_month: 1.476, rate: 0.3, rate_unit: '$/GB ingested (assumed)', cost_month: 0.44, basis: '1,000,000,000 bytes = 1 GB',
    },
    evidence: [{
      label: 'DEBUG/TRACE logs for orders in SigNoz Logs Explorer',
      deeplink: "http://localhost:8080/logs/logs-explorer?relativeTime=1440m&filter=service.name+%3D+%27orders%27+AND+severity_number+%3C+9",
      filter: "service.name = 'orders' AND severity_number < 9",
      raw_query: "SELECT resources_string['service.name'] AS service, countIf(severity_number>0 AND severity_number<9) AS debug_logs FROM signoz_logs.distributed_logs_v2 WHERE ... GROUP BY service",
    }],
    safety: {
      safe: true,
      proof: '0 dashboards / 0 alerts / 0 saved views reference DEBUG-level logs for service orders.',
      references: [], checked: { dashboards: 0, alerts: 0 },
    },
    patch_path: 'collector/generated/T1.yaml',
    fix: {},
    verification: {},
    error: '',
  },
]

// Mutable clone so mock apply/verify/unapply visibly change state during design preview.
const mockStore: Finding[] = JSON.parse(JSON.stringify(mockFindings))
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
      ...init,
    })
  } catch (e) {
    throw new Error(`auditor unreachable at ${API_BASE} — is it running (make up) and NEXT_PUBLIC_AUDITOR_URL set?`)
  }
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`
    try { const j = await resp.json(); if (j?.detail) detail = j.detail } catch {}
    throw new Error(detail)
  }
  return resp.json() as Promise<T>
}

class SpanSaverAPI {
  /** POST /audit — run all detectors + fixgen, return findings (detected -> fix_ready). */
  async runAudit(): Promise<Finding[]> {
    if (USE_MOCK) { await wait(700); return JSON.parse(JSON.stringify(mockStore)) }
    const data = await req<AuditResponse>('/audit', { method: 'POST' })
    return data.findings
  }

  /** GET /findings — last audit's findings without re-running detectors. */
  async listFindings(): Promise<Finding[]> {
    if (USE_MOCK) { return JSON.parse(JSON.stringify(mockStore)) }
    const data = await req<AuditResponse>('/findings')
    return data.findings
  }

  async getFinding(id: string): Promise<Finding> {
    if (USE_MOCK) {
      const f = mockStore.find((x) => x.id === id.toUpperCase())
      if (!f) throw new Error(`${id} not found — run an audit first`)
      return JSON.parse(JSON.stringify(f))
    }
    return req<Finding>(`/findings/${id}`)
  }

  async applyFinding(id: string): Promise<ActionResponse> {
    if (USE_MOCK) { await wait(600); const f = mockStore.find((x) => x.id === id.toUpperCase()); if (f) f.status = 'applied'; return { status: 'applied' } }
    return req<ActionResponse>(`/apply/${id}`, { method: 'POST' })
  }

  async verifyFinding(id: string): Promise<ActionResponse> {
    if (USE_MOCK) {
      await wait(900)
      const f = mockStore.find((x) => x.id === id.toUpperCase())
      if (f) {
        const isLlm = f.domain === 'llm'
        const headline = isLlm
          ? { metric: 'cacheable repeat calls', unit: 'repeats/min', kind: 'rate', before: 10, after: 0.4, drop_pct: 96 }
          : { metric: 'debug-log ingest', unit: 'bytes/min', kind: 'rate', before: 34167, after: 1420, drop_pct: 95.8 }
        const integrity = { ok: true, dashboards_resolved: 3, alerts_resolved: 2 }
        f.status = 'verified'
        f.verification = {
          id: f.id, passed: true, threshold_drop_pct: 25, headline, integrity,
          banner: `Verified: ${integrity.dashboards_resolved} dashboards and ${integrity.alerts_resolved} alerts intact — ${headline.metric} down ${Math.round(headline.drop_pct)}%.`,
        }
      }
      return { status: 'verified', verification: f?.verification }
    }
    return req<ActionResponse>(`/verify/${id}`, { method: 'POST' })
  }

  async unapplyFinding(id: string): Promise<ActionResponse> {
    if (USE_MOCK) { await wait(500); const f = mockStore.find((x) => x.id === id.toUpperCase()); if (f) { f.status = 'fix_ready'; f.verification = {} } return { status: 'unapplied' } }
    return req<ActionResponse>(`/unapply/${id}`, { method: 'POST' })
  }

  /** POST /explain/{id} — the auditor's OWN traced LLM call. Real usage + cost, gen_ai spans to
   *  SigNoz. Mock returns a canned explanation so the UI is demoable without a key. */
  async explainFinding(id: string): Promise<ExplainResponse> {
    if (USE_MOCK) {
      await wait(900)
      const f = mockStore.find((x) => x.id === id.toUpperCase())
      return {
        id: id.toUpperCase(),
        explanation: {
          explanation:
            `${id.toUpperCase()} is wasted spend: ${f?.summary ?? 'a detected leak'} The fix is safe because ${f?.safety?.proof ?? 'nothing referenced depends on the dropped data'} — so applying it stops the waste without breaking anything you rely on.`,
          provider: 'anthropic', model: 'claude-opus-4-8',
          usage: { input_tokens: 210, output_tokens: 96 },
          cost_usd: 0.0021, rate_unit: '$/Mtok in|out (assumed)',
          traced: "gen_ai spans emitted to SigNoz as service 'spansaver-auditor' (Agent Ops)",
        },
      }
    }
    return req<ExplainResponse>(`/explain/${id}`, { method: 'POST' })
  }

  async health(): Promise<HealthResponse> {
    if (USE_MOCK) { return { status: 'ok', clickhouse: { ok: true, error: '' }, signoz_api: { ok: true, error: '' }, applied_patches: [] } }
    return req<HealthResponse>('/health')
  }
}

export const api = new SpanSaverAPI()
