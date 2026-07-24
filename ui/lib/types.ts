// Types mirror the SpanSaver auditor's Finding.to_dict() exactly (auditor/telemetry_auditor/
// findings.py). Do not invent fields — the UI renders only what the backend measures.

export type Status = 'detected' | 'fix_ready' | 'applied' | 'verified' | 'failed'
export type Domain = 'telemetry' | 'llm'

export interface Evidence {
  label: string
  deeplink: string // SigNoz explorer URL
  filter: string
  raw_query: string // exact ClickHouse query run
}

export interface Safety {
  safe: boolean
  proof: string
  references?: unknown[]
  checked?: Record<string, unknown>
}

export interface Fix {
  kind?: string // "config" for LLM env-flip fixes
  target?: string
  diff?: string // unified diff text (LLM fixes)
  apply?: string
  note?: string
  path?: string
}

// money.py output — always carries cost_month + rate + the inputs so the UI shows its work.
export interface Money {
  cost_month: number
  rate_unit?: string
  extrapolation_factor?: number
  window_hours?: number
  // ingest ($/GB)
  bytes_window?: number
  gb_window?: number
  gb_month?: number
  rate?: number
  basis?: string
  // per-million (metrics datapoints / spans)
  count_window?: number
  count_month?: number
  // tokens ($/Mtok)
  input_tokens_window?: number
  output_tokens_window?: number
  input_tokens_month?: number
  output_tokens_month?: number
  rate_in?: number
  rate_out?: number
  [k: string]: unknown
}

export interface Finding {
  id: string // "T1", "L1", ...
  domain: Domain
  title: string
  summary: string
  service: string
  status: Status
  measured: Record<string, unknown>
  money: Money
  evidence: Evidence[]
  safety: Safety
  patch_path: string // collector-patch fixes (telemetry)
  fix: Fix // config-diff fixes (llm)
  verification: Record<string, unknown>
  error: string
}

// /explain/{id} — the auditor's own traced LLM call (explainer.py). cost_usd is priced with the
// same assumed $/Mtok rates as findings; the call emits gen_ai spans to SigNoz (spansaver-auditor).
export interface Explanation {
  explanation: string
  provider: string
  model: string
  usage: { input_tokens: number; output_tokens: number }
  cost_usd: number
  rate_unit: string
  traced: string
}

export interface ExplainResponse {
  id: string
  explanation: Explanation
}

export interface AuditResponse {
  count: number
  findings: Finding[]
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  clickhouse: { ok: boolean; error: string }
  signoz_api: { ok: boolean; error: string }
  applied_patches: string[]
}

export interface ActionResponse {
  status: string
  [k: string]: unknown
}
