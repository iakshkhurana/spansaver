'use client'

import Link from 'next/link'
import { Finding } from '@/lib/types'
import { moneyMo } from '@/lib/format'
import { ChevronRight, ShieldCheck, ShieldAlert } from 'lucide-react'

export function statusClass(status: string): string {
  switch (status) {
    case 'fix_ready': return 'bg-accent/15 border border-accent/40 text-accent'
    case 'applied': return 'bg-secondary/15 border border-secondary/40 text-secondary neon-green'
    case 'verified': return 'bg-primary/20 border border-primary/50 text-primary neon-cyan'
    case 'failed': return 'bg-destructive/15 border border-destructive/40 text-destructive'
    default: return 'bg-muted/30 border border-muted/50 text-muted-foreground'
  }
}

function domainClass(domain: string): string {
  return domain === 'llm'
    ? 'bg-secondary/10 border border-secondary/30 text-secondary'
    : 'bg-primary/10 border border-primary/30 text-primary'
}

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const sorted = [...findings].sort((a, b) => (b.money?.cost_month ?? 0) - (a.money?.cost_month ?? 0))

  return (
    <div className="border border-primary/20 rounded-lg overflow-hidden bg-gradient-to-b from-card/50 to-card/30 backdrop-blur-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-primary/15 bg-gradient-to-r from-primary/10 to-secondary/5 text-xs text-muted-foreground tracking-widest uppercase font-semibold">
            <th className="text-left py-3 px-4">ID</th>
            <th className="text-left py-3 px-4">Domain</th>
            <th className="text-left py-3 px-4">Leak</th>
            <th className="text-left py-3 px-4">Service</th>
            <th className="text-right py-3 px-4">$ / month</th>
            <th className="text-center py-3 px-4">Status</th>
            <th className="text-center py-3 px-4">Safe</th>
            <th className="py-3 px-4"></th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((f) => (
            <tr key={f.id} className="border-b border-primary/10 hover:bg-primary/5 transition-all duration-200 group">
              <td className="py-4 px-4">
                <span className="font-bold text-primary tracking-widest">{f.id}</span>
              </td>
              <td className="py-4 px-4">
                <span className={`text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded ${domainClass(f.domain)}`}>{f.domain}</span>
              </td>
              <td className="py-4 px-4 max-w-md">
                <Link href={`/leak/${f.id}`} className="block">
                  <div className="font-medium text-foreground group-hover:neon-cyan">{f.title}</div>
                  <div className="text-xs text-muted-foreground line-clamp-1 mt-1">{f.summary}</div>
                </Link>
              </td>
              <td className="py-4 px-4">
                <span className="text-xs font-mono text-muted-foreground">{f.service || '—'}</span>
              </td>
              <td className="py-4 px-4 text-right">
                <span className="text-sm font-bold font-mono neon-green">{moneyMo(f.money?.cost_month)}</span>
              </td>
              <td className="py-4 px-4 text-center">
                <span className={`text-[10px] font-bold tracking-widest uppercase px-3 py-1.5 rounded-md inline-block ${statusClass(f.status)}`}>
                  {f.status.replace('_', ' ')}
                </span>
              </td>
              <td className="py-4 px-4 text-center">
                {f.safety?.safe
                  ? <ShieldCheck className="w-4 h-4 text-primary mx-auto" />
                  : <ShieldAlert className="w-4 h-4 text-destructive mx-auto" />}
              </td>
              <td className="py-4 px-4 text-right">
                <Link href={`/leak/${f.id}`} className="opacity-40 group-hover:opacity-100 transition-opacity inline-block">
                  <ChevronRight className="w-4 h-4 text-primary" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
