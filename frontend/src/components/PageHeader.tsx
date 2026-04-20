import type { ReactNode } from 'react'

type PageHeaderProps = {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl space-y-3">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[color:var(--color-accent)]">
            {eyebrow}
          </p>
        ) : null}
        <div className="space-y-2">
          <h1 className="text-4xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)] md:text-5xl">
            {title}
          </h1>
          <p className="max-w-2xl text-base leading-7 text-[color:var(--color-mist)] md:text-lg">
            {description}
          </p>
        </div>
      </div>
      {actions ? <div className="flex items-center gap-3">{actions}</div> : null}
    </div>
  )
}