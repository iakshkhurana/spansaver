'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

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

  const navLink = (href: string, label: string) => (
    <Link href={href}
      className={`px-4 py-2 text-xs tracking-wide rounded-md transition-all duration-200 ${
        isActive(href)
          ? 'text-primary neon-cyan bg-primary/15 border border-primary/40'
          : 'text-muted-foreground hover:text-primary/80 hover:bg-primary/5'
      }`}>
      {label}
    </Link>
  )

  return (
    <header className="border-b border-primary/20 bg-background/60 backdrop-blur-xl sticky top-0 z-40 scan-line">
      <div className="container mx-auto px-6 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary/50 flex items-center justify-center text-xs font-bold text-primary-foreground group-hover:shadow-lg group-hover:shadow-primary/50 transition-all">
            {'>_'}
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-bold neon-cyan tracking-widest">SPANSAVER</span>
            <span className="text-[10px] text-muted-foreground tracking-wider">telemetry &amp; llm waste auditor</span>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {navLink('/', 'Mission Control')}
          {navLink('/judge', 'Judge Mode')}
        </nav>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className={`w-1.5 h-1.5 rounded-full ${online === false ? 'bg-destructive' : 'bg-secondary animate-pulse'}`} />
          <span className={online === false ? 'text-destructive' : 'text-secondary'}>
            {online === null ? 'CONNECTING' : online ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </header>
  )
}
