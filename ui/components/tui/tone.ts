// Shared semantic tones for the v2 TUI dashboard. Maps a status/meaning to the existing
// theme tokens (globals.css) so v2 stays consistent with the rest of the app's palette.
export type Tone = 'cyan' | 'green' | 'amber' | 'red' | 'violet' | 'muted'

export const TONE_TEXT: Record<Tone, string> = {
  cyan: 'text-primary',
  green: 'text-secondary',
  amber: 'text-accent',
  red: 'text-destructive',
  violet: 'text-[color:var(--color-violet)]',
  muted: 'text-muted-foreground',
}

export const TONE_BG: Record<Tone, string> = {
  cyan: 'bg-primary',
  green: 'bg-secondary',
  amber: 'bg-accent',
  red: 'bg-destructive',
  violet: 'bg-[color:var(--color-violet)]',
  muted: 'bg-muted-foreground',
}

// A Finding.status → tone, used by the findings table, the log widget, and the status pills.
export function statusTone(status: string): Tone {
  switch (status) {
    case 'verified': return 'green'
    case 'applied': return 'violet'
    case 'fix_ready': return 'amber'
    case 'failed': return 'red'
    default: return 'cyan' // detected
  }
}
