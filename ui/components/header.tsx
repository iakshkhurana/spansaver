'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { ThemeToggle } from '@/components/tui/theme-toggle'

export function Header() {
  const pathname = usePathname()
  const [online, setOnline] = useState<boolean | null>(null)
  const isActive = (path: string) => pathname === path

  useEffect(() => {
    let alive = true
    const check = async () => {
      try { const h = await api.health(); if (alive) setOnline(h.status === 'ok' || h.status === 'degraded') }
      catch { if (alive) setOnline(false) }
    }
    check()
    const t = setInterval(check, 5000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  const navLink = (href: string, sigil: string, label: string) => (
    <Link href={href}
      className={`mono px-3 py-1.5 text-xs tracking-wide rounded-md transition-colors ${
        isActive(href)
          ? 'text-foreground bg-[var(--overlay)]'
          : 'text-muted-foreground hover:text-foreground hover:bg-[var(--overlay)]'
      }`}>
      <span className="text-primary mr-1.5">{sigil}</span>{label}
    </Link>
  )

  return (
    <header className="border-b border-border bg-background/70 backdrop-blur-xl sticky top-0 z-40">
      <div className="container mx-auto px-6 h-16 flex items-center justify-between gap-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg border border-border bg-[var(--overlay)] flex items-center justify-center group-hover:border-primary/60 transition-colors">
              <span className="mono text-primary text-sm font-bold">{'>_'}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-base font-bold tracking-tight text-foreground">SpanSaver</span>
              <span className="mono hidden sm:inline text-[10px] text-muted-foreground uppercase tracking-[0.2em]">waste auditor</span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
            {navLink('/', '>', 'Mission Control')}
            {navLink('/judge', '@', 'Judge Mode')}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="mono flex items-center gap-2 text-[11px] tracking-wide px-3 py-1.5 rounded-full border border-border bg-[var(--overlay)]">
            <span className={`live-dot w-1.5 h-1.5 rounded-full ${online === false ? 'bg-destructive text-destructive' : 'bg-secondary text-secondary'}`} />
            <span className={online === false ? 'text-destructive' : 'text-muted-foreground'}>
              {online === null ? 'CONNECTING' : online ? 'AUDITOR ONLINE' : 'AUDITOR OFFLINE'}
            </span>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
