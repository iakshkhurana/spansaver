import { ReactNode } from 'react'
import { Tone, TONE_TEXT } from './tone'

// A boxed "widget" whose title sits notched in the top border — the terminal/btop hallmark.
// `meta` is an optional right-aligned label on the same border line (e.g. "PID: 8392").
export function Panel({
  title, meta, tone = 'cyan', children, className = '',
}: {
  title: string
  meta?: ReactNode
  tone?: Tone
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`tui tui-panel ${className}`}>
      <span className={`tui-title ${TONE_TEXT[tone]}`}>{title}</span>
      {meta != null && <span className="tui-meta">{meta}</span>}
      <div className="p-4 pt-5">{children}</div>
    </section>
  )
}
