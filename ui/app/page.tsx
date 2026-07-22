'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Header } from '@/components/header'
import { FindingsTable } from '@/components/findings-table'
import { TerminalCLI } from '@/components/terminal-cli'
import { api } from '@/lib/api'
import { Finding } from '@/lib/types'
import { moneyMo } from '@/lib/format'
import { AlertTriangle, Play, Loader2, ArrowRight, ShieldCheck } from 'lucide-react'

export default function Dashboard() {
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

  const totalMonthly = findings.reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const verified = findings.filter((f) => f.status === 'verified')
  const recovered = verified.reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const safeCount = findings.filter((f) => f.safety?.safe).length

  const stats: Array<{ v: string; l: string; c: string }> = [
    { v: moneyMo(totalMonthly), l: 'leaking / mo', c: 'text-secondary' },
    { v: String(findings.length), l: 'findings', c: 'text-primary' },
    { v: moneyMo(recovered), l: 'recovered / mo', c: 'text-[color:var(--color-violet)]' },
    { v: `${safeCount}/${findings.length || 0}`, l: 'safe to fix', c: 'text-accent' },
  ]

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="container mx-auto px-6 py-12 md:py-16 space-y-16">
        {/* ── Hero: headline (left) + working console (right) ── */}
        <section className="grid lg:grid-cols-[1.05fr_1fr] gap-10 items-center">
          <div className="space-y-7">
            <div className="mono inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-white/[0.02] text-[11px] tracking-widest uppercase text-muted-foreground">
              <span className="live-dot w-1.5 h-1.5 rounded-full bg-secondary text-secondary" />
              detect · prove · fix · verify
            </div>

            <h1 className="text-5xl md:text-6xl font-bold tracking-tight leading-[1.05]">
              Telemetry &amp;<br />
              <span className="gradient-text">LLM Waste</span> Auditor
            </h1>

            <p className="text-muted-foreground text-base md:text-lg max-w-xl leading-relaxed">
              Find the money leaking from your observability + LLM stack — logs nobody reads,
              orphan metrics, cardinality bombs, cacheable prompts. Every fix is proven safe
              and verified against real SigNoz metrics.
            </p>

            <div className="flex items-center gap-3 flex-wrap">
              <button onClick={runAudit} disabled={auditing}
                className="inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-60">
                {auditing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                {auditing ? 'Auditing…' : 'Run Audit'}
              </button>
              <Link href="/judge"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-lg border border-border bg-white/[0.02] text-foreground font-medium text-sm hover:bg-white/[0.05] transition-colors">
                Judge Mode <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="mono flex flex-wrap items-baseline gap-x-7 gap-y-3 pt-2">
              {stats.map((s) => (
                <div key={s.l} className="flex items-baseline gap-2">
                  <span className={`text-2xl font-bold ${s.c}`}>{s.v}</span>
                  <span className="text-[11px] text-muted-foreground uppercase tracking-widest">{s.l}</span>
                </div>
              ))}
            </div>
          </div>

          {/* The working console lives on the front — same audit/apply/verify as the buttons. */}
          <div className="h-[30rem]">
            <TerminalCLI findings={findings} onRefresh={refresh} />
            <p className="mono text-[11px] text-muted-foreground mt-2 text-center">
              live console · type <span className="text-primary">help</span> · runs against the auditor API
            </p>
          </div>
        </section>

        {error && (
          <div className="mono p-4 border border-destructive/40 bg-destructive/10 rounded-lg text-sm text-destructive">
            <div className="font-bold mb-1 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> AUDITOR ERROR</div>
            {error}
          </div>
        )}

        {/* ── Detected leaks ── */}
        <section className="space-y-5">
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <div className="mono text-[11px] text-muted-foreground uppercase tracking-[0.2em] mb-1">Findings</div>
              <h2 className="text-2xl font-bold tracking-tight">Detected leaks</h2>
            </div>
            {verified.length > 0 && (
              <div className="mono inline-flex items-center gap-2 text-xs text-secondary">
                <ShieldCheck className="w-4 h-4" /> {verified.length} verified · {moneyMo(recovered)}/mo sealed
              </div>
            )}
          </div>

          {loading ? (
            <div className="text-center py-16 mono text-sm text-muted-foreground">
              <Loader2 className="w-6 h-6 mx-auto animate-spin mb-3 text-primary" /> connecting to auditor…
            </div>
          ) : findings.length > 0 ? (
            <FindingsTable findings={findings} />
          ) : (
            <div className="cyber-card p-12 text-center space-y-2">
              <p className="text-sm text-muted-foreground">
                No findings yet — hit <span className="text-primary font-semibold">Run Audit</span> or type{' '}
                <span className="mono text-primary">audit</span> in the console.
              </p>
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-border mt-8">
        <div className="container mx-auto px-6 py-6 mono text-[11px] text-muted-foreground flex items-center justify-between flex-wrap gap-2">
          <span>SpanSaver — detect · prove · fix · verify</span>
          <span>every number is a live query against SigNoz</span>
        </div>
      </footer>
    </div>
  )
}
