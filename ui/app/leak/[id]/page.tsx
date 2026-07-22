'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Header } from '@/components/header'
import { CodeDiff } from '@/components/code-diff'
import { ActionBar } from '@/components/action-bar'
import { MoneyMath } from '@/components/money-math'
import { statusClass } from '@/components/findings-table'
import { api } from '@/lib/api'
import { Finding } from '@/lib/types'
import { moneyMo } from '@/lib/format'
import { ArrowLeft, ArrowRight, ShieldCheck, ShieldAlert, ExternalLink, Loader2, CheckCircle2 } from 'lucide-react'

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-bold text-muted-foreground tracking-widest uppercase">{title}</h2>
      {children}
    </section>
  )
}

function Measured({ measured }: { measured: Record<string, unknown> }) {
  const scalars = Object.entries(measured).filter(([, v]) => typeof v !== 'object')
  const arrays = Object.entries(measured).filter(([, v]) => Array.isArray(v)) as [string, Record<string, unknown>[]][]
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {scalars.map(([k, v]) => (
          <div key={k} className="border border-primary/15 bg-card/40 rounded-md p-3">
            <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">{k.replace(/_/g, ' ')}</div>
            <div className="text-sm font-mono font-bold text-foreground">{typeof v === 'number' ? v.toLocaleString() : String(v)}</div>
          </div>
        ))}
      </div>
      {arrays.map(([k, rows]) => rows.length > 0 && typeof rows[0] === 'object' && (
        <div key={k} className="border border-primary/15 rounded-md overflow-hidden">
          <div className="bg-primary/10 px-3 py-2 text-[10px] uppercase tracking-widest text-muted-foreground">{k.replace(/_/g, ' ')} ({rows.length})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead><tr className="text-muted-foreground border-b border-primary/10">
                {Object.keys(rows[0]).map((c) => <th key={c} className="text-left py-2 px-3 font-normal">{c.replace(/_/g, ' ')}</th>)}
              </tr></thead>
              <tbody>
                {rows.slice(0, 6).map((r, i) => (
                  <tr key={i} className="border-b border-primary/5">
                    {Object.values(r).map((v, j) => <td key={j} className="py-2 px-3 text-foreground truncate max-w-[16rem]">{typeof v === 'number' ? v.toLocaleString() : String(v)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}

interface Verification {
  passed?: boolean
  banner?: string
  threshold_drop_pct?: number
  headline?: { metric: string; unit: string; kind: string; before: number; after: number; drop_pct: number }
  integrity?: { ok: boolean; dashboards_resolved?: number; alerts_resolved?: number; error?: string }
}

const num = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 1 })

function VerifyPanel({ ver }: { ver: Verification }) {
  const passed = !!ver.passed
  const h = ver.headline
  const integ = ver.integrity
  const good = passed // banner tone follows pass/fail
  return (
    <Panel title="Verification (before → after)">
      {/* Green/red banner — the demo line, read live off real queries */}
      <div className={`border rounded-md p-4 flex items-center gap-3 ${good ? 'border-primary/50 bg-primary/10' : 'border-destructive/50 bg-destructive/10'}`}>
        {good ? <CheckCircle2 className="w-6 h-6 text-primary flex-shrink-0" /> : <ShieldAlert className="w-6 h-6 text-destructive flex-shrink-0" />}
        <p className={`text-sm md:text-base font-bold ${good ? 'neon-green' : 'text-destructive'}`}>{ver.banner}</p>
      </div>

      {/* before → after for the headline signal */}
      {h && (
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] items-center gap-3 mt-3">
          <div className="border border-primary/15 bg-card/40 rounded-md p-4 text-center">
            <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">before</div>
            <div className="text-2xl font-bold font-mono text-foreground">{num(h.before)}</div>
            <div className="text-[10px] text-muted-foreground mt-1">{h.unit}</div>
          </div>
          <div className="flex flex-col items-center gap-1 px-2">
            <ArrowRight className="w-5 h-5 text-primary" />
            <span className={`text-xs font-bold font-mono ${h.drop_pct > 0 ? 'neon-green' : 'text-destructive'}`}>
              {h.drop_pct > 0 ? '↓' : ''}{num(Math.abs(h.drop_pct))}%
            </span>
          </div>
          <div className="border border-primary/40 bg-primary/5 rounded-md p-4 text-center">
            <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">after</div>
            <div className="text-2xl font-bold font-mono neon-green">{num(h.after)}</div>
            <div className="text-[10px] text-muted-foreground mt-1">{h.unit}</div>
          </div>
        </div>
      )}
      {h && <p className="text-[11px] text-muted-foreground mt-2 font-mono text-center">{h.metric}</p>}

      {/* integrity — nothing broke */}
      {integ && (
        <div className="mt-3 flex items-center gap-2 text-xs font-mono">
          {integ.ok
            ? <><ShieldCheck className="w-4 h-4 text-primary" /><span className="text-muted-foreground">{integ.dashboards_resolved ?? 0} dashboards · {integ.alerts_resolved ?? 0} alerts still resolve — nothing broke.</span></>
            : <><ShieldAlert className="w-4 h-4 text-destructive" /><span className="text-destructive">integrity check failed: {integ.error}</span></>}
        </div>
      )}

      <details className="group mt-3">
        <summary className="text-[11px] text-muted-foreground cursor-pointer hover:text-primary">raw verification payload</summary>
        <pre className="mt-2 p-3 bg-background/60 border border-primary/10 rounded text-[11px] font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap">{JSON.stringify(ver, null, 2)}</pre>
      </details>
    </Panel>
  )
}

export default function LeakDetail() {
  const id = (useParams().id as string)
  const [finding, setFinding] = useState<Finding | null>(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try { setFinding(await api.getFinding(id)); setError(null) }
    catch (e) { setError(e instanceof Error ? e.message : 'not found') }
    finally { setLoading(false) }
  }, [id])

  useEffect(() => { load() }, [load])

  const act = async (fn: (id: string) => Promise<unknown>) => {
    try { setActing(true); await fn.call(api, id); await load() }
    catch (e) { setError(e instanceof Error ? e.message : 'action failed') }
    finally { setActing(false) }
  }

  if (loading) return (
    <div className="min-h-screen bg-background"><Header />
      <main className="container mx-auto px-6 py-20 text-center"><Loader2 className="w-8 h-8 text-primary mx-auto animate-spin" /></main>
    </div>
  )

  if (!finding) return (
    <div className="min-h-screen bg-background"><Header />
      <main className="container mx-auto px-6 py-16 text-center space-y-4">
        <ShieldAlert className="w-10 h-10 text-destructive mx-auto" />
        <p className="text-muted-foreground font-mono text-sm">{error || `${id} not found — run an audit first.`}</p>
        <Link href="/" className="text-primary text-sm hover:underline">← back to Mission Control</Link>
      </main>
    </div>
  )

  const f = finding
  const ver = f.verification && Object.keys(f.verification).length > 0 ? f.verification : null

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="container mx-auto px-6 py-8 space-y-8 max-w-5xl">
        <Link href="/" className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-primary transition-colors">
          <ArrowLeft className="w-4 h-4" /> Mission Control
        </Link>

        {error && <div className="p-3 border border-destructive/40 bg-destructive/10 rounded text-xs text-destructive font-mono">{error}</div>}

        {/* Header */}
        <section className="space-y-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-2xl font-bold text-primary tracking-widest">{f.id}</span>
                <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded bg-primary/10 border border-primary/30 text-primary">{f.domain}</span>
                <span className={`text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded ${statusClass(f.status)}`}>{f.status.replace('_', ' ')}</span>
              </div>
              <h1 className="text-2xl md:text-3xl font-bold">{f.title}</h1>
              <p className="text-muted-foreground text-sm max-w-2xl">{f.summary}</p>
              {f.service && <p className="text-xs font-mono text-muted-foreground">service: <span className="text-secondary">{f.service}</span></p>}
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold neon-green font-mono">{moneyMo(f.money?.cost_month)}</div>
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest">recoverable</div>
            </div>
          </div>
        </section>

        <MoneyMath money={f.money} />

        <Panel title="Measured (real query output)"><Measured measured={f.measured} /></Panel>

        <Panel title="Safety proof">
          <div className={`border rounded-md p-4 flex gap-3 ${f.safety?.safe ? 'border-primary/40 bg-primary/5' : 'border-destructive/40 bg-destructive/10'}`}>
            {f.safety?.safe ? <ShieldCheck className="w-5 h-5 text-primary flex-shrink-0" /> : <ShieldAlert className="w-5 h-5 text-destructive flex-shrink-0" />}
            <div className="space-y-2">
              <p className="text-sm text-foreground">{f.safety?.proof}</p>
              {f.safety?.checked && Object.keys(f.safety.checked).length > 0 && (
                <div className="text-[11px] font-mono text-muted-foreground">
                  {Object.entries(f.safety.checked).map(([k, v]) => <span key={k} className="mr-4">{k}={String(v)}</span>)}
                </div>
              )}
            </div>
          </div>
        </Panel>

        <Panel title="The fix">
          <CodeDiff diff={f.fix?.diff} path={f.patch_path} />
          {(f.fix?.apply || f.fix?.note) && (
            <p className="text-xs text-muted-foreground mt-2 font-mono">{f.fix.apply}{f.fix.note ? ` · ${f.fix.note}` : ''}</p>
          )}
        </Panel>

        <Panel title="Evidence">
          {f.evidence?.map((ev, i) => (
            <div key={i} className="border border-primary/20 rounded-md p-4 space-y-3">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <span className="text-sm text-foreground">{ev.label}</span>
                <a href={ev.deeplink} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-primary hover:neon-cyan transition-colors">
                  OPEN IN SIGNOZ <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
              <details className="group">
                <summary className="text-[11px] text-muted-foreground cursor-pointer hover:text-primary">raw ClickHouse query</summary>
                <pre className="mt-2 p-3 bg-background/60 border border-primary/10 rounded text-[11px] font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap">{ev.raw_query}</pre>
              </details>
            </div>
          ))}
        </Panel>

        {ver && <VerifyPanel ver={ver as Verification} />}

        <ActionBar finding={f} isLoading={acting}
          onApply={() => act(api.applyFinding)} onVerify={() => act(api.verifyFinding)} onUnapply={() => act(api.unapplyFinding)}>
          {f.status === 'fix_ready' && 'Fix generated & proven safe — ready to apply.'}
          {f.status === 'applied' && 'Applied. Run verify to confirm the leak stopped and nothing broke.'}
          {f.status === 'verified' && 'Verified on real metrics. Leak sealed.'}
          {f.status === 'detected' && (f.error || 'Detected — no fix generated.')}
        </ActionBar>
      </main>
    </div>
  )
}
