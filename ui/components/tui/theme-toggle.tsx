'use client'

import { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'

// Toggles data-theme on <html> and persists to localStorage. The no-flash init script in
// layout.tsx sets the attribute before paint; this just flips + remembers it.
export function ThemeToggle({ className = '' }: { className?: string }) {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')

  useEffect(() => {
    const cur = (document.documentElement.getAttribute('data-theme') as 'dark' | 'light') || 'dark'
    setTheme(cur)
  }, [])

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', next)
    try { localStorage.setItem('theme', next) } catch { /* ignore */ }
    setTheme(next)
  }

  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title="Toggle light / dark"
      className={`inline-flex items-center justify-center w-8 h-8 rounded-md border border-border bg-[var(--overlay)] text-muted-foreground hover:text-foreground hover:border-primary/40 active:scale-[0.96] transition ${className}`}
    >
      {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  )
}
