// Presentation helpers. Numbers are always the backend's measured values — these only format.

export function money(n: number | undefined): string {
  const v = n ?? 0
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function moneyMo(n: number | undefined): string {
  return `${money(n)}/mo`
}

export function num(n: number | undefined): string {
  return (n ?? 0).toLocaleString()
}

export function tokens(n: number | undefined): string {
  return (n ?? 0).toLocaleString()
}

export function pct(n: number | undefined): string {
  return `${Math.round((n ?? 0) * (Math.abs(n ?? 0) <= 1 ? 100 : 1))}%`
}

export function bytes(n: number | undefined): string {
  let v = n ?? 0
  for (const unit of ['B', 'KB', 'MB', 'GB', 'TB']) {
    if (v < 1024 || unit === 'TB') return `${v.toFixed(unit === 'B' ? 0 : 1)} ${unit}`
    v /= 1024
  }
  return `${v} TB`
}

export const STATUS_ORDER: Record<string, number> = {
  detected: 0, fix_ready: 1, applied: 2, verified: 3, failed: -1,
}
