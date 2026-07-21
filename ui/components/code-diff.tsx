'use client'

import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

// Renders a unified-diff string (fix.diff): '-' red, '+' green, '#' comment/dim. Used for the LLM
// config fixes; collector-patch fixes pass their patch_path via the `path` prop instead.
export function CodeDiff({ diff, path }: { diff?: string; path?: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    await navigator.clipboard.writeText(diff ?? path ?? '')
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (!diff) {
    return (
      <div className="border border-primary/30 bg-card/40 rounded-md p-4 text-sm font-mono">
        <div className="text-xs text-muted-foreground uppercase tracking-widest mb-2">Collector patch</div>
        <div className="text-primary">{path || 'generated on apply'}</div>
        <p className="text-xs text-muted-foreground mt-2">
          A scoped OTel filter processor, deep-merged onto the baseline at collector reload. Error-status
          records are never dropped.
        </p>
      </div>
    )
  }

  return (
    <div className="border border-primary/30 rounded-md overflow-hidden bg-background/60">
      <div className="flex items-center justify-between bg-primary/10 border-b border-primary/30 px-3 py-2">
        <span className="text-xs font-bold text-primary tracking-widest uppercase">Config diff</span>
        <button onClick={copy} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors">
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      <pre className="p-3 text-xs overflow-x-auto leading-relaxed">
        {diff.split('\n').map((line, i) => {
          const cls = line.startsWith('+') ? 'text-secondary'
            : line.startsWith('-') ? 'text-destructive'
            : line.startsWith('#') ? 'text-muted-foreground'
            : 'text-foreground'
          return <div key={i} className={`${cls} whitespace-pre-wrap`}>{line || ' '}</div>
        })}
      </pre>
    </div>
  )
}
