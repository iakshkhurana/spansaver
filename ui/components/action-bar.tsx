'use client'

import { Finding } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { CheckCircle2, RotateCcw, Zap } from 'lucide-react'
import { ReactNode } from 'react'

interface ActionBarProps {
  finding: Finding
  onApply?: () => void
  onVerify?: () => void
  onUnapply?: () => void
  isLoading?: boolean
  children?: ReactNode
}

// Lifecycle: detected -> fix_ready -> applied -> verified (LEAK-CATALOG). Apply is enabled once a
// fix is ready; verify once applied; unapply once applied/verified (reversibility is demoed).
export function ActionBar({ finding, onApply, onVerify, onUnapply, isLoading, children }: ActionBarProps) {
  const canApply = finding.status === 'fix_ready'
  const canVerify = finding.status === 'applied'
  const canUnapply = finding.status === 'applied' || finding.status === 'verified'

  return (
    <div className="sticky bottom-0 flex flex-col md:flex-row gap-3 items-start md:items-center justify-between border-t border-primary/20 bg-background/80 backdrop-blur-xl pt-4 pb-4">
      <div className="text-xs text-muted-foreground">{children}</div>

      <div className="flex gap-2 w-full md:w-auto">
        {canApply && (
          <Button onClick={onApply} disabled={isLoading} size="sm"
            className="flex-1 md:flex-none gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-bold">
            <Zap className="w-4 h-4" />
            {isLoading ? 'APPLYING…' : 'APPLY FIX'}
          </Button>
        )}

        {canVerify && (
          <Button onClick={onVerify} disabled={isLoading} size="sm"
            className="flex-1 md:flex-none gap-2 bg-secondary hover:bg-secondary/90 text-secondary-foreground font-bold">
            <CheckCircle2 className="w-4 h-4" />
            {isLoading ? 'VERIFYING…' : 'VERIFY'}
          </Button>
        )}

        {canUnapply && (
          <Button onClick={onUnapply} disabled={isLoading} variant="outline" size="sm"
            className="flex-1 md:flex-none gap-2 border-primary/40">
            <RotateCcw className="w-4 h-4" />
            UNAPPLY
          </Button>
        )}

        {finding.status === 'verified' && (
          <div className="flex items-center gap-2 px-3 py-2 border border-primary/50 bg-primary/10 rounded-md text-xs font-bold text-primary neon-cyan">
            <CheckCircle2 className="w-4 h-4" /> VERIFIED
          </div>
        )}
      </div>
    </div>
  )
}
