'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { ThemeToggle } from './theme-toggle'
import { Play, Loader2, ArrowUpRight } from 'lucide-react'

function HealthPill({ label, ok }: { label: string; ok: boolean | null }) {
  const tone = ok === null ? 'text-muted-foreground' : ok ? 'text-secondary' : 'text-destructive'
  const dot = ok === null ? 'bg-muted-foreground' : ok ? 'bg-secondary' : 'bg-destructive'
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${dot} ${ok ? 'pulse-dot' : ''}`} />
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-semibold ${tone}`}>{ok === null ? '···' : ok ? 'OK' : 'DOWN'}</span>
    </span>
  )
}

// Chrome only: identity · backend health · clock · theme · actions. The numbers live in the
// dashboard body (KPIs), not here — no duplication.
export function StatusBar({ onRunAudit, auditing }: { onRunAudit: () => void; auditing: boolean }) {
  const [clock, setClock] = useState('--:--:--')
  const [health, setHealth] = useState<{ ch: boolean; api: boolean } | null>(null)

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString('en-GB', { hour12: false }))
    tick()
    const t = setInterval(tick, 1000)
    let alive = true
    const poll = () => api.health()
      .then((h) => { if (alive) setHealth({ ch: h.clickhouse.ok, api: h.signoz_api.ok }) })
      .catch(() => { if (alive) setHealth({ ch: false, api: false }) })
    poll()
    const h = setInterval(poll, 8000)
    return () => { alive = false; clearInterval(t); clearInterval(h) }
  }, [])

  return (
    <header className="tui sticky top-0 z-40 -mx-4 md:-mx-6 px-4 md:px-6 h-14 flex items-center justify-between gap-4 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-8 h-8 rounded-md border border-primary/40 bg-primary/10 grid place-items-center shrink-0">
          <span className="text-primary text-sm font-bold">{'>_'}</span>
        </div>
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-[15px] font-bold tracking-widest text-foreground">SPANSAVER<span className="text-muted-foreground">_UI</span></span>
          <span className="hidden lg:inline text-[10px] text-muted-foreground tracking-widest truncate">mission control</span>
        </div>
      </div>

      <div className="flex items-center gap-3 md:gap-4">
        <div className="hidden sm:flex items-center gap-3 text-[11px]">
          <HealthPill label="CH" ok={health?.ch ?? null} />
          <span className="text-muted-foreground/30">│</span>
          <HealthPill label="API" ok={health?.api ?? null} />
          <span className="hidden md:inline figure text-muted-foreground tabular-nums ml-1">{clock}</span>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button onClick={onRunAudit} disabled={auditing}
            className="inline-flex items-center gap-2 h-8 px-3 text-[11px] font-bold rounded-md border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 active:scale-[0.98] transition disabled:opacity-50 tracking-widest uppercase">
            {auditing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{auditing ? 'auditing' : 'run audit'}</span>
          </button>
          <Link href="/judge"
            className="inline-flex items-center gap-1.5 h-8 px-3 text-[11px] font-bold rounded-md border border-border bg-[var(--overlay)] text-muted-foreground hover:text-foreground hover:border-primary/40 active:scale-[0.98] transition tracking-widest uppercase">
            judge <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </header>
  )
}

export function StatusFooter({ findingCount, loading }: { findingCount: number; loading: boolean }) {
  return (
    <div className="tui flex items-center justify-between gap-3 flex-wrap pt-2 text-[10.5px] text-muted-foreground">
      <span className="inline-flex items-center gap-2">
        <span className="text-secondary">{loading ? 'connecting to auditor…' : `✓ ${findingCount} finding${findingCount === 1 ? '' : 's'} loaded`}</span>
        <span className="tui-caret bg-secondary/70 pulse-dot" />
      </span>
      <span className="tracking-wide">every number is a live query against SigNoz</span>
    </div>
  )
}
