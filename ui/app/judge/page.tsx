'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Panel } from '@/components/tui/panel'
import { ThemeToggle } from '@/components/tui/theme-toggle'
import { Tone, TONE_TEXT } from '@/components/tui/tone'
import { api } from '@/lib/api'
import { Finding } from '@/lib/types'
import { money } from '@/lib/format'
import { ArrowLeft, ArrowUpRight, ShieldCheck, ShieldAlert, Terminal } from 'lucide-react'

// The judge's cheat-sheet — every criterion mapped to one-click evidence (mirrors docs/JUDGING-MAP.md),
// over live proof numbers. Track: AI & Agent Observability.
const CRITERIA: { n: number; title: string; tone: Tone; show: string; links: { l: string; href: string }[] }[] = [
  { n: 1, title: 'Potential Impact', tone: 'green', show: 'Real $/month recovered across the two universal bills — telemetry bytes + LLM tokens — measured live, not estimated.', links: [{ l: 'mission control', href: '/' }] },
  { n: 2, title: 'Creativity & Innovation', tone: 'violet', show: 'A self-healing agent that closes the loop on AI + infra waste, with a safety-proof step — and it audits its own AI cost via a real traced LLM call.', links: [{ l: 'L1 cache proof', href: '/leak/L1' }, { l: 'T2 safety proof', href: '/leak/T2' }] },
  { n: 3, title: 'Technical Excellence', tone: 'cyan', show: 'ClickHouse introspection, OTTL patch generation with validation + rollback, before/after verify with a dashboard/alert integrity sweep.', links: [{ l: 'top finding', href: '/' }] },
  { n: 4, title: 'Best Use of SigNoz', tone: 'cyan', show: 'Reads ClickHouse + the dashboards/alerts API; writes collector patches + importable dashboards, and its own gen_ai spans back into SigNoz (spansaver-auditor).', links: [] },
  { n: 5, title: 'User Experience', tone: 'amber', show: 'One-screen leak report, evidence deep-links, one-tap Apply, a before→after green banner, a live command console, and Judge Mode itself.', links: [{ l: 'console', href: '/' }] },
  { n: 6, title: 'Presentation', tone: 'green', show: 'A 3-minute demo where every claim is clicked, not asserted; `make demo` reproduces the whole detect→prove→fix→verify loop hands-free.', links: [] },
]

function Kpi({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="tile p-4 text-center">
      <div className={`figure text-3xl md:text-4xl font-bold leading-none ${tone}`}>{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-[0.18em] mt-2">{label}</div>
    </div>
  )
}

export default function JudgeMode() {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      try { setFindings(await api.listFindings()) } catch { /* offline is fine on this page */ } finally { setLoading(false) }
    })()
  }, [])

  const total = findings.reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const recovered = findings.filter((f) => f.status === 'verified').reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const safe = findings.filter((f) => f.safety?.safe).length
  const top = [...findings].sort((a, b) => (b.money?.cost_month ?? 0) - (a.money?.cost_month ?? 0)).slice(0, 3)

  return (
    <div className="tui min-h-screen bg-background text-foreground grid-bg">
      <div className="container mx-auto px-4 md:px-6 max-w-[1100px]">
        {/* top bar */}
        <header className="sticky top-0 z-40 -mx-4 md:-mx-6 px-4 md:px-6 h-14 flex items-center justify-between gap-4 border-b border-border bg-background/80 backdrop-blur-xl">
          <Link href="/" className="inline-flex items-center gap-2 text-[12px] text-muted-foreground hover:text-foreground transition tracking-widest uppercase">
            <ArrowLeft className="w-4 h-4" /> console
          </Link>
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground uppercase tracking-[0.2em]">
            <span className="hidden sm:inline">AI &amp; Agent Observability</span>
            <ThemeToggle />
          </div>
        </header>

        <main className="py-8 md:py-12 space-y-8">
          {/* hero */}
          <section className="text-center space-y-3 pt-2">
            <div className="inline-flex items-center gap-2 text-[10px] tracking-[0.2em] uppercase text-muted-foreground border border-border rounded-full px-3 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary pulse-dot" /> judge mode · live evidence
            </div>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground">SpanSaver</h1>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl mx-auto leading-relaxed">
              A self-healing agent that watches your AI + infra through SigNoz, detects waste, proves a fix is safe,
              applies it, and verifies the result — closing the loop with real metrics.
            </p>
          </section>

          {/* live proof */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => <div key={i} className="tile p-4 h-[92px]"><div className="h-8 skeleton" /></div>)
            ) : (
              <>
                <Kpi label="leaking / month" value={money(total)} tone="text-secondary" />
                <Kpi label="leaks found" value={String(findings.length)} tone="text-foreground" />
                <Kpi label="safe to fix" value={`${safe}/${findings.length || 0}`} tone="text-primary" />
                <Kpi label="sealed / month" value={money(recovered)} tone="text-[color:var(--color-violet)]" />
              </>
            )}
          </section>

          {/* criteria → evidence */}
          <Panel title="judging_map" tone="cyan" meta="criterion → live proof">
            <div className="grid md:grid-cols-2 gap-3">
              {CRITERIA.map((c) => (
                <div key={c.n} className="tile p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className={`figure text-sm font-bold w-6 h-6 grid place-items-center rounded border border-[var(--hairline)] ${TONE_TEXT[c.tone]}`}>{c.n}</span>
                    <h3 className="text-[13px] font-bold tracking-wide text-foreground">{c.title}</h3>
                  </div>
                  <p className="text-[11.5px] text-muted-foreground leading-relaxed flex-1">{c.show}</p>
                  {c.links.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {c.links.map((lk) => (
                        <Link key={lk.href + lk.l} href={lk.href}
                          className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded border border-[var(--hairline)] bg-[var(--overlay)] hover:border-primary/40 transition ${TONE_TEXT[c.tone]}`}>
                          {lk.l} <ArrowUpRight className="w-3 h-3" />
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Panel>

          {/* money shots */}
          <Panel title="money_shots" tone="green" meta="top findings by $">
            {loading ? (
              <div className="space-y-2.5">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 skeleton" />)}</div>
            ) : top.length === 0 ? (
              <div className="py-8 text-center text-[12px] text-muted-foreground">
                no findings yet — run an audit from <Link href="/" className="text-primary hover:underline">Mission Control</Link>.
              </div>
            ) : (
              <div className="space-y-2.5">
                {top.map((f) => (
                  <Link key={f.id} href={`/leak/${f.id}`}
                    className="tile block p-4 hover:border-primary/40 transition group">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="text-lg font-bold text-primary tracking-widest">{f.id}</span>
                        <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border ${f.domain === 'llm' ? 'text-secondary border-secondary/30' : 'text-primary border-primary/30'}`}>{f.domain}</span>
                        {f.safety?.safe
                          ? <span className="inline-flex items-center gap-1 text-[10px] text-secondary uppercase tracking-widest"><ShieldCheck className="w-3.5 h-3.5" /> safe</span>
                          : <span className="inline-flex items-center gap-1 text-[10px] text-destructive uppercase tracking-widest"><ShieldAlert className="w-3.5 h-3.5" /> review</span>}
                      </div>
                      <div className="figure text-xl font-bold text-secondary">{money(f.money?.cost_month)}<span className="text-[11px] text-muted-foreground font-normal">/mo</span></div>
                    </div>
                    <div className="mt-2 text-[13px] font-semibold text-foreground group-hover:text-primary transition-colors">{f.title}</div>
                    <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">{f.summary}</p>
                  </Link>
                ))}
              </div>
            )}
          </Panel>

          {/* the loop */}
          <div className="tui-scan tile flex items-center justify-center gap-3 sm:gap-5 py-3 flex-wrap text-[11px] uppercase tracking-[0.18em]">
            {['detect', 'prove', 'fix', 'verify'].map((s, i) => (
              <span key={s} className="inline-flex items-center gap-3 sm:gap-5">
                <span className={i === 3 ? 'text-secondary font-bold' : 'text-foreground font-bold'}>{s}</span>
                {i < 3 && <span className="text-primary">→</span>}
              </span>
            ))}
          </div>

          <div className="flex items-center justify-center gap-2 pt-2">
            <Link href="/" className="inline-flex items-center gap-2 h-9 px-4 text-[11px] font-bold rounded-md border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 transition tracking-widest uppercase">
              <Terminal className="w-3.5 h-3.5" /> open mission control
            </Link>
          </div>
        </main>
      </div>
    </div>
  )
}
