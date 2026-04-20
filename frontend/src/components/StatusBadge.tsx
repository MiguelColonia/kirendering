import type { ReactNode } from 'react'

type StatusBadgeProps = {
  tone?: 'neutral' | 'good' | 'warn' | 'accent'
  children: ReactNode
}

const toneClasses: Record<NonNullable<StatusBadgeProps['tone']>, string> = {
  neutral: 'border-[color:var(--color-line)] bg-white/70 text-[color:var(--color-ink)]',
  good: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warn: 'border-amber-200 bg-amber-50 text-amber-700',
  accent: 'border-[color:var(--color-accent)]/20 bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]',
}

export function StatusBadge({ tone = 'neutral', children }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${toneClasses[tone]}`}
    >
      {children}
    </span>
  )
}