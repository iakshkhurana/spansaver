import { Tone, TONE_TEXT, TONE_BG } from './tone'

// A thin, rounded progress bar with a subtle track. `value`/`max` are measured numbers.
export function Meter({
  value, max = 1, tone = 'cyan', className = '',
}: {
  value: number
  max?: number
  tone?: Tone
  className?: string
}) {
  const frac = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0
  return (
    <div className={`relative h-1.5 w-full rounded-full bg-[var(--track)] overflow-hidden ${className}`}>
      <div
        className={`absolute inset-y-0 left-0 rounded-full ${TONE_BG[tone]} transition-[width] duration-500 ease-out`}
        style={{ width: `${frac * 100}%` }}
      />
    </div>
  )
}

// LABEL ──────[bar]────── value
export function MeterRow({
  label, value, max = 1, tone = 'cyan', right,
}: {
  label: string
  value: number
  max?: number
  tone?: Tone
  right?: string
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="grid grid-cols-[6rem_1fr_3.75rem] items-center gap-3">
      <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground truncate">{label}</span>
      <Meter value={value} max={max} tone={tone} />
      <span className={`figure text-[12px] font-semibold text-right ${TONE_TEXT[tone]}`}>{right ?? `${pct}%`}</span>
    </div>
  )
}
