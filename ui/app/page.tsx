'use client'

import { useState, useEffect, useCallback } from 'react'
import { Header } from '@/components/header'
import { KPIRow } from '@/components/kpi-row'
import { FindingsTable } from '@/components/findings-table'
import { TerminalCLI } from '@/components/terminal-cli'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { Finding } from '@/lib/types'
import { moneyMo } from '@/lib/format'
import { Activity, AlertTriangle, Play, Loader2 } from 'lucide-react'

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
  const recovered = findings.filter((f) => f.status === 'verified').reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const safeCount = findings.filter((f) => f.safety?.safe).length

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="container mx-auto px-6 py-10 space-y-10">
        <section className="flex items-end justify-between gap-4 flex-wrap">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="w-2 h-8 bg-gradient-to-b from-primary to-secondary rounded-full" />
              <h1 className="text-4xl md:text-5xl font-bold neon-cyan tracking-tight">Mission Control</h1>
            </div>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl">
              Money leaking from your observability stack — detected, proven safe, fixed, and verified with real metrics.
            </p>
          </div>
          <Button onClick={runAudit} disabled={auditing}
            className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-bold tracking-widest">
            {auditing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {auditing ? 'AUDITING…' : 'RUN AUDIT'}
          </Button>
        </section>

        <KPIRow
          items={[
            { label: 'Leaking / month', value: moneyMo(totalMonthly), highlight: totalMonthly > 0 },
            { label: 'Findings', value: findings.length },
            { label: 'Recovered / month', value: moneyMo(recovered), secondary: `${findings.filter(f => f.status === 'verified').length} verified` },
            { label: 'Safe to fix', value: `${safeCount}/${findings.length}` },
          ]}
        />

        {error && (
          <div className="p-4 border border-destructive/50 bg-destructive/10 rounded-lg text-sm text-destructive font-mono">
            <div className="font-bold mb-1 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> AUDITOR ERROR</div>
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 space-y-4">
            <Activity className="w-10 h-10 text-primary mx-auto animate-pulse" />
            <p className="text-muted-foreground text-sm">Connecting to auditor…</p>
          </div>
        ) : (
          <>
            <section className="space-y-4">
              <h2 className="text-xl font-bold neon-cyan">Detected leaks</h2>
              {findings.length > 0 ? (
                <FindingsTable findings={findings} />
              ) : (
                <div className="p-12 text-center text-muted-foreground border border-primary/15 rounded-lg bg-card/30 space-y-3">
                  <p className="text-sm">No findings yet. Hit <span className="text-primary font-bold">RUN AUDIT</span> to scan the stack.</p>
                </div>
              )}
            </section>

            <section className="space-y-4">
              <h2 className="text-xl font-bold neon-cyan">Control console</h2>
              <p className="text-xs text-muted-foreground -mt-2">Type <span className="text-primary">help</span>. Runs the same audit/apply/verify as the buttons.</p>
              <TerminalCLI findings={findings} onRefresh={refresh} />
            </section>
          </>
        )}
      </main>
    </div>
  )
}
