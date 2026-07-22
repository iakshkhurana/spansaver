'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Finding } from '@/lib/types'
import { api } from '@/lib/api'
import { moneyMo } from '@/lib/format'

interface Props {
  findings: Finding[]
  onRefresh?: () => void | Promise<void>
}

const BANNER = [
  'SPANSAVER // control console',
  'telemetry + llm waste auditor — detect · prove · fix · verify',
  'type "help" for commands',
  '',
]

export function TerminalCLI({ findings, onRefresh }: Props) {
  const router = useRouter()
  const [input, setInput] = useState('')
  const [lines, setLines] = useState<string[]>(BANNER)
  const [cmds, setCmds] = useState<string[]>([])
  const [histIdx, setHistIdx] = useState(-1)
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [lines])

  const print = (...out: string[]) => setLines((p) => [...p, ...out])
  const find = (id?: string) => findings.find((f) => f.id.toLowerCase() === (id ?? '').toLowerCase())

  const HELP = [
    '', 'COMMANDS', '  audit               run all detectors',
    '  ls                  list findings', '  show <id>           finding summary + safety',
    '  apply <id>          apply the fix', '  verify <id>         re-measure after apply',
    '  unapply <id>        revert the fix', '  open <id>           open detail page',
    '  evidence <id>       open SigNoz deep-link', '  health              backend status',
    '  clear', '',
  ]

  async function run(raw: string) {
    const trimmed = raw.trim()
    if (!trimmed) return
    print(`$ ${trimmed}`)
    setCmds((p) => [...p, trimmed]); setHistIdx(-1); setInput('')
    const [cmd, arg] = [trimmed.split(/\s+/)[0].toLowerCase(), trimmed.split(/\s+/)[1]]

    try {
      setBusy(true)
      switch (cmd) {
        case 'help': print(...HELP); break
        case 'clear': setLines([]); break
        case 'health': {
          const h = await api.health()
          print(`  status      ${h.status}`,
            `  clickhouse  ${h.clickhouse.ok ? 'ok' : 'FAIL ' + h.clickhouse.error}`,
            `  signoz_api  ${h.signoz_api.ok ? 'ok' : 'FAIL ' + h.signoz_api.error}`,
            `  applied     ${h.applied_patches.join(', ') || '(none)'}`, '')
          break
        }
        case 'audit': {
          print('  running detectors…')
          const fs = await api.runAudit()
          print(`  ✓ ${fs.length} finding(s)`, ...fs.map((f) => `    ${f.id.padEnd(4)} ${moneyMo(f.money?.cost_month).padStart(11)}  ${f.title}`), '')
          await onRefresh?.(); break
        }
        case 'ls': case 'findings': {
          if (!findings.length) { print('  (no findings — run audit)', ''); break }
          print('  ID   $ / MONTH    STATUS       LEAK',
            ...findings.map((f) => `  ${f.id.padEnd(4)} ${moneyMo(f.money?.cost_month).padStart(10)}  ${f.status.padEnd(11)} ${f.title}`), '')
          break
        }
        case 'show': {
          const f = find(arg); if (!f) { print(`  ✗ ${arg ?? ''} not found`, ''); break }
          print(`  ${f.id} · ${f.title}  [${f.status}]`, `  ${f.summary}`,
            `  cost        ${moneyMo(f.money?.cost_month)}`,
            `  safe        ${f.safety?.safe ? 'yes' : 'NO'} — ${f.safety?.proof ?? ''}`, '')
          break
        }
        case 'apply': case 'verify': case 'unapply': {
          const f = find(arg); if (!f) { print(`  ✗ ${arg ?? ''} not found`, ''); break }
          const fn = cmd === 'apply' ? api.applyFinding : cmd === 'verify' ? api.verifyFinding : api.unapplyFinding
          const res = await fn.call(api, f.id)
          print(`  ✓ ${cmd} ${f.id} → ${res.status}`, '')
          await onRefresh?.(); break
        }
        case 'open': {
          const f = find(arg); if (!f) { print(`  ✗ ${arg ?? ''} not found`, ''); break }
          print(`  opening /leak/${f.id}…`, ''); router.push(`/leak/${f.id}`); break
        }
        case 'evidence': {
          const f = find(arg); const url = f?.evidence?.[0]?.deeplink
          if (!url) { print('  ✗ no evidence link', ''); break }
          print(`  opening SigNoz…`, ''); window.open(url, '_blank'); break
        }
        default: print(`  ✗ unknown command: ${cmd}`, '  type "help"', '')
      }
    } catch (e) {
      print(`  ✗ ${e instanceof Error ? e.message : 'command failed'}`, '')
    } finally { setBusy(false) }
  }

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') run(input)
    else if (e.key === 'ArrowUp') { e.preventDefault(); const i = Math.min(histIdx + 1, cmds.length - 1); if (i >= 0) { setHistIdx(i); setInput(cmds[cmds.length - 1 - i] ?? '') } }
    else if (e.key === 'ArrowDown') { e.preventDefault(); const i = histIdx - 1; if (i < 0) { setHistIdx(-1); setInput('') } else { setHistIdx(i); setInput(cmds[cmds.length - 1 - i] ?? '') } }
  }

  const lineClass = (l: string) =>
    l.startsWith('  ✓') ? 'text-secondary' : l.startsWith('  ✗') ? 'text-destructive'
    : l.startsWith('$') ? 'text-primary' : (l === 'COMMANDS' || l.startsWith('  ID')) ? 'text-accent'
    : 'text-muted-foreground'

  return (
    <div className="mono overflow-hidden flex flex-col h-full min-h-[22rem] rounded-xl border border-primary/25 bg-card ring-1 ring-primary/10 shadow-[0_0_60px_-18px_rgba(56,189,248,0.35)]"
      onClick={() => inputRef.current?.focus()}>
      <div className="border-b border-primary/15 px-4 py-2.5 flex items-center justify-between bg-primary/[0.06]">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
          <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
          <span className="w-3 h-3 rounded-full bg-[#28c840]" />
          <span className="ml-2 text-[11px] text-primary/90 tracking-wide">auditor://console</span>
        </div>
        <span className={`flex items-center gap-1.5 text-[10px] tracking-widest uppercase ${busy ? 'text-accent' : 'text-secondary'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${busy ? 'bg-accent' : 'bg-secondary'}`} />
          {busy ? 'running' : 'ready'}
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto thin-scroll p-4 dot-grid">
        {lines.map((l, i) => (
          <div key={i} className={`text-[12px] whitespace-pre-wrap break-words leading-relaxed ${lineClass(l)}`}>{l || ' '}</div>
        ))}
      </div>

      <div className="border-t border-primary/15 px-4 py-3 flex items-center gap-2 bg-primary/[0.04]">
        <span className="text-primary text-sm">➜</span>
        <span className="text-muted-foreground text-xs">spansaver</span>
        <input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
          disabled={busy} spellCheck={false}
          style={{ caretColor: 'rgb(56 189 248)' }}
          className="flex-1 bg-transparent outline-none text-xs text-foreground placeholder-muted-foreground/50 ml-1"
          placeholder={busy ? 'working…' : 'type a command — try: help'} />
      </div>
    </div>
  )
}
