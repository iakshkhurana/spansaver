'use client'

import { Money } from '@/lib/types'
import { money as fmtMoney, moneyMo, num, bytes } from '@/lib/format'
import { TrendingDown } from 'lucide-react'

// Shows the math, never a bare number (golden rule #2): measured X in window -> x factor -> $/mo
// at {rate} {rate_unit}. The rate is the only assumption and is always labelled.
export function MoneyMath({ money }: { money: Money }) {
  const steps: { label: string; value: string }[] = []

  if (money.gb_window !== undefined) {
    // ingest ($/GB)
    steps.push({ label: 'measured in window', value: `${bytes(money.bytes_window)} (${money.gb_window} GB)` })
    steps.push({ label: `× ${money.extrapolation_factor} (to 30 days)`, value: `${money.gb_month} GB/mo` })
    steps.push({ label: `× rate ${fmtMoney(money.rate)} ${money.rate_unit ?? ''}`, value: moneyMo(money.cost_month) })
  } else if (money.input_tokens_window !== undefined) {
    // tokens ($/Mtok)
    steps.push({ label: 'wasted tokens in window (in / out)', value: `${num(money.input_tokens_window)} / ${num(money.output_tokens_window)}` })
    steps.push({ label: `× ${money.extrapolation_factor} (to 30 days)`, value: `${num(money.input_tokens_month)} / ${num(money.output_tokens_month)} tok/mo` })
    steps.push({ label: `× rate in ${fmtMoney(money.rate_in)} · out ${fmtMoney(money.rate_out)} per Mtok`, value: moneyMo(money.cost_month) })
  } else if (money.count_window !== undefined) {
    // per-million (metrics / spans)
    steps.push({ label: 'measured in window', value: `${num(money.count_window)}` })
    steps.push({ label: `× ${money.extrapolation_factor} (to 30 days)`, value: `${num(money.count_month)}/mo` })
    steps.push({ label: `× rate ${fmtMoney(money.rate)} ${money.rate_unit ?? ''}`, value: moneyMo(money.cost_month) })
  } else {
    steps.push({ label: 'projected monthly cost', value: moneyMo(money.cost_month) })
  }

  return (
    <div className="space-y-3">
      <div className="border border-primary/30 rounded-md overflow-hidden">
        {steps.map((s, i) => (
          <div key={i} className={`flex items-center justify-between px-4 py-3 font-mono text-sm ${i < steps.length - 1 ? 'border-b border-primary/10' : 'bg-primary/5'}`}>
            <span className="text-muted-foreground text-xs">{s.label}</span>
            <span className={i === steps.length - 1 ? 'font-bold neon-green' : 'text-foreground'}>{s.value}</span>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3 border border-primary/40 bg-primary/5 rounded-md p-4">
        <TrendingDown className="w-6 h-6 text-primary flex-shrink-0" />
        <div>
          <div className="text-3xl font-bold neon-cyan font-mono">{moneyMo(money.cost_month)}</div>
          <div className="text-xs text-muted-foreground mt-1">
            recoverable · {money.rate_unit ?? 'assumed rate'} — measured volume, assumed price
          </div>
        </div>
      </div>
    </div>
  )
}
