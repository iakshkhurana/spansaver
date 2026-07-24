'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { TerminalCLI } from '@/components/terminal-cli'
import { Panel } from '@/components/tui/panel'
import { MeterRow } from '@/components/tui/meter'
import { StatusBar, StatusFooter } from '@/components/tui/status-bar'
import { TONE_TEXT, statusTone } from '@/components/tui/tone'
import { api } from '@/lib/api'
import { Finding } from '@/lib/types'
import { money } from '@/lib/format'
import { AlertTriangle, ChevronRight, ShieldCheck, ShieldAlert, Inbox, RotateCw } from 'lucide-react'

// v2 · Mission Control — same real /audit + /findings data as the main UI, in a calm operator
// layout: KPIs → findings (primary) → console + status. Every number is derived from findings.

const statusLabel = (f: Finding) =>
  f.status === 'fix_ready' && f.fix?.kind === 'recommendation' ? 'recommend' : f.status.replace('_', ' ')

function DomainTag({ domain }: { domain: string }) {
  const llm = domain === 'llm'
  return (
    <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border ${llm ? 'text-secondary border-secondary/30' : 'text-primary border-primary/30'}`}>
      {llm ? 'llm' : 'tel'}
    </span>
  )
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: string }) {
  return (
    <div className="tile p-4">
      <div className="text-[9px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className={`figure text-[1.7rem] font-bold leading-tight mt-1.5 ${tone}`}>{value}</div>
      <div className="text-[10px] text-muted-foreground/70 mt-1 truncate">{sub}</div>
    </div>
  )
}

export default function DashboardV2() {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)
  const [auditing, setAuditing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try { setFindings(await api.listFindings()); setError(null) }
    catch (e) { setError(e instanceof Error ? e.message : 'failed to load findings') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const runAudit = async () => {
    try { setAuditing(true); setError(null); setFindings(await api.runAudit()) }
    catch (e) { setError(e instanceof Error ? e.message : 'audit failed') }
    finally { setAuditing(false) }
  }

  const n = findings.length
  const totalMonthly = findings.reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const verified = findings.filter((f) => f.status === 'verified')
  const recovered = verified.reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const safeCount = findings.filter((f) => f.safety?.safe).length
  const appliedCount = findings.filter((f) => f.status === 'applied' || f.status === 'verified').length
  const telemetryMo = findings.filter((f) => f.domain === 'telemetry').reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const llmMo = findings.filter((f) => f.domain === 'llm').reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const sorted = [...findings].sort((a, b) => (b.money?.cost_month ?? 0) - (a.money?.cost_month ?? 0))

  return (
    <div className="tui min-h-screen bg-background text-foreground grid-bg">
      <div className="container mx-auto px-4 md:px-6 max-w-[1240px]">
        <StatusBar onRunAudit={runAudit} auditing={auditing} />

        <main className="py-6 space-y-6">
          {error && (
            <div className="border border-destructive/40 bg-destructive/[0.08] rounded-lg px-3.5 py-3 text-[12px] text-destructive flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 min-w-0"><AlertTriangle className="w-4 h-4 shrink-0" /> <b className="tracking-widest">AUDITOR_ERROR</b> <span className="text-destructive/80 truncate">{error}</span></span>
              <button onClick={refresh} className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest border border-destructive/40 rounded px-2 py-1 hover:bg-destructive/10 transition shrink-0"><RotateCw className="w-3 h-3" /> retry</button>
            </div>
          )}

          {/* KPIs — the single source of headline numbers */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => <div key={i} className="tile p-4 h-[92px]"><div className="h-7 skeleton mt-2" /></div>)
            ) : (
              <>
                <Kpi label="monthly leak" value={money(totalMonthly)} sub="recoverable / month" tone="text-secondary" />
                <Kpi label="annualized" value={money(totalMonthly * 12)} sub="/ yr · ×12 projection" tone="text-[color:var(--color-violet)]" />
                <Kpi label="findings" value={String(n)} sub={`${safeCount} safe to fix`} tone="text-foreground" />
                <Kpi label="verified" value={String(verified.length)} sub={`${money(recovered)} sealed`} tone="text-primary" />
              </>
            )}
          </div>

          {/* findings (primary) · console + status (secondary) */}
          <div className="grid lg:grid-cols-12 gap-6 items-start">
            <div className="lg:col-span-8">
              <Panel title="active_findings" tone="cyan" meta={loading || n === 0 ? undefined : `${n} · sorted by $`}>
                {loading ? (
                  <div className="space-y-2.5 py-1">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 skeleton" />)}</div>
                ) : n === 0 ? (
                  <div className="py-16 text-center">
                    <Inbox className="w-8 h-8 mx-auto text-muted-foreground/40 mb-3" />
                    <p className="text-[13px] text-foreground">No findings yet</p>
                    <p className="text-[11px] text-muted-foreground mt-1.5">Hit <span className="text-primary font-bold">run audit</span> above, or type <span className="text-primary">audit</span> in the console →</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-[12.5px] min-w-[540px]">
                      <thead>
                        <tr className="text-[9px] text-muted-foreground uppercase tracking-[0.16em] border-b border-border">
                          <th className="text-left font-semibold py-2.5 pr-3">id</th>
                          <th className="text-left font-semibold py-2.5 pr-3">leak</th>
                          <th className="text-left font-semibold py-2.5 pr-3">domain</th>
                          <th className="text-left font-semibold py-2.5 pr-3">status</th>
                          <th className="text-center font-semibold py-2.5 pr-3">safe</th>
                          <th className="text-right font-semibold py-2.5 pr-2">$ / mo</th>
                          <th className="py-2.5 w-5"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {sorted.map((f) => (
                          <tr key={f.id} className="border-b border-border/50 last:border-0 hover:bg-[var(--overlay)] transition-colors group">
                            <td className="py-3.5 pr-3"><Link href={`/leak/${f.id}`} className="font-bold text-primary tracking-widest rounded">{f.id}</Link></td>
                            <td className="py-3.5 pr-3 max-w-[19rem]">
                              <Link href={`/leak/${f.id}`} className="block rounded">
                                <div className="text-foreground group-hover:text-primary transition-colors truncate">{f.title}</div>
                                <div className="text-[10.5px] text-muted-foreground truncate mt-0.5">{f.summary}</div>
                              </Link>
                            </td>
                            <td className="py-3.5 pr-3"><DomainTag domain={f.domain} /></td>
                            <td className="py-3.5 pr-3">
                              <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border border-[var(--hairline)] bg-[var(--overlay)] ${TONE_TEXT[statusTone(f.status)]}`}>{statusLabel(f)}</span>
                            </td>
                            <td className="py-3.5 pr-3 text-center">
                              {f.safety?.safe ? <ShieldCheck className="w-4 h-4 text-secondary mx-auto" /> : <ShieldAlert className="w-4 h-4 text-destructive mx-auto" />}
                            </td>
                            <td className="py-3.5 pr-2 text-right figure font-bold text-secondary">{money(f.money?.cost_month)}</td>
                            <td className="py-3.5 text-right">
                              <Link href={`/leak/${f.id}`} className="opacity-0 group-hover:opacity-100 transition-opacity inline-block rounded" aria-label={`Open ${f.id}`}><ChevronRight className="w-4 h-4 text-primary" /></Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            </div>

            <div className="lg:col-span-4 space-y-6">
              <div className="h-[22rem]">
                <TerminalCLI findings={findings} onRefresh={refresh} />
              </div>

              <Panel title="status" tone="cyan">
                <div className="space-y-3">
                  <MeterRow label="safe" value={safeCount} max={n || 1} tone="cyan" right={`${safeCount}/${n || 0}`} />
                  <MeterRow label="verified" value={verified.length} max={n || 1} tone="green" right={`${verified.length}/${n || 0}`} />
                  <MeterRow label="applied" value={appliedCount} max={n || 1} tone="violet" right={`${appliedCount}/${n || 0}`} />
                </div>
                <div className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-3 text-[11px]">
                  <div className="flex items-baseline justify-between"><span className="text-muted-foreground uppercase tracking-widest text-[9px]">telemetry</span><span className="figure font-bold text-primary">{money(telemetryMo)}</span></div>
                  <div className="flex items-baseline justify-between"><span className="text-muted-foreground uppercase tracking-widest text-[9px]">llm</span><span className="figure font-bold text-secondary">{money(llmMo)}</span></div>
                </div>
              </Panel>
            </div>
          </div>

          <StatusFooter findingCount={n} loading={loading} />
        </main>
      </div>
    </div>
  )
}
