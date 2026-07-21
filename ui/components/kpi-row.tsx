'use client'

import { ReactNode } from 'react'

interface KPIRowProps {
  items: Array<{
    label: string
    value: string | ReactNode
    unit?: string
    secondary?: string
    highlight?: boolean
  }>
}

export function KPIRow({ items }: KPIRowProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {items.map((item, idx) => (
        <div
          key={idx}
          className={`p-4 border rounded-lg transition-all duration-300 group cursor-default ${
            item.highlight
              ? 'border-primary/50 bg-gradient-to-br from-primary/10 to-primary/5 shadow-lg shadow-primary/20 hover:border-primary/80 hover:shadow-primary/40'
              : 'border-primary/15 bg-gradient-to-br from-card/60 to-card/40 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/10'
          }`}
        >
          <div className="text-xs text-muted-foreground tracking-wider mb-2 uppercase font-semibold">{item.label}</div>
          <div className={`text-2xl font-bold font-mono ${item.highlight ? 'neon-cyan' : 'text-foreground group-hover:text-primary transition-colors'}`}>
            {item.value}
            {item.unit && <span className="text-sm text-muted-foreground ml-1 font-normal">{item.unit}</span>}
          </div>
          {item.secondary && <div className="text-xs text-muted-foreground mt-2 font-mono">{item.secondary}</div>}
        </div>
      ))}
    </div>
  )
}
