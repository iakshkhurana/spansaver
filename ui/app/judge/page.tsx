'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Header } from '@/components/header'
import { api } from '@/lib/api'
import { Finding } from '@/lib/types'
import { moneyMo } from '@/lib/format'
import { ShieldCheck, ShieldAlert, Loader2, ArrowRight } from 'lucide-react'

export default function JudgeMode() {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      try { setFindings(await api.listFindings()) } catch {} finally { setLoading(false) }
    })()
  }, [])

  const total = findings.reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const recovered = findings.filter((f) => f.status === 'verified').reduce((s, f) => s + (f.money?.cost_month ?? 0), 0)
  const top = [...findings].sort((a, b) => (b.money?.cost_month ?? 0) - (a.money?.cost_month ?? 0)).slice(0, 3)

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="container mx-auto px-6 py-12 space-y-12 max-w-5xl">
        <section className="text-center space-y-3">
          <h1 className="text-5xl md:text-6xl font-bold neon-cyan tracking-tight">SpanSaver</h1>
          <p className="text-muted-foreground text-base md:text-lg">Find the money leaking from an engineering stack — and prove it's safe to fix.</p>
        </section>

        {loading ? (
          <div className="text-center py-20"><Loader2 className="w-8 h-8 text-primary mx-auto animate-spin" /></div>
        ) : (
          <>
            <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                { label: 'Leaking / month', value: moneyMo(total) },
                { label: 'Leaks found', value: String(findings.length) },
                { label: 'Recovered / month', value: moneyMo(recovered) },
              ].map((s) => (
                <div key={s.label} className="cyber-card p-8 text-center">
                  <div className="text-4xl md:text-5xl font-bold neon-green font-mono">{s.value}</div>
                  <div className="text-xs text-muted-foreground uppercase tracking-widest mt-3">{s.label}</div>
                </div>
              ))}
            </section>

            <section className="space-y-4">
              {top.map((f) => (
                <Link key={f.id} href={`/leak/${f.id}`}
                  className="block cyber-card p-6 hover:border-primary/50 transition-all group">
                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-primary tracking-widest">{f.id}</span>
                      <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded bg-primary/10 border border-primary/30 text-primary">{f.domain}</span>
                      {f.safety?.safe
                        ? <span className="inline-flex items-center gap-1 text-[10px] text-primary uppercase tracking-widest"><ShieldCheck className="w-3.5 h-3.5" /> safe</span>
                        : <span className="inline-flex items-center gap-1 text-[10px] text-destructive uppercase tracking-widest"><ShieldAlert className="w-3.5 h-3.5" /> review</span>}
                    </div>
                    <div className="text-2xl font-bold neon-green font-mono">{moneyMo(f.money?.cost_month)}</div>
                  </div>
                  <h3 className="text-lg font-bold mt-3">{f.title}</h3>
                  <p className="text-sm text-muted-foreground mt-1">{f.summary}</p>
                  <div className="mt-3 text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1">
                    see the proof <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </Link>
              ))}
              {top.length === 0 && (
                <div className="text-center text-muted-foreground text-sm py-12 border border-primary/15 rounded-lg">
                  No findings yet — run an audit from <Link href="/" className="text-primary hover:underline">Mission Control</Link>.
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
