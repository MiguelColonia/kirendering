import { ArrowRight, DraftingCompass, FolderKanban } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'

export function LandingPage() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <section className="panel-surface overflow-hidden rounded-[2rem] p-6 md:p-8">
        <PageHeader
          eyebrow={t('landing.hero.eyebrow')}
          title={t('landing.hero.title')}
          description={t('landing.hero.description')}
          actions={
            <div className="flex flex-wrap gap-3">
              <Link
                to="/projekte/neu"
                className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-white"
              >
                {t('landing.hero.primary_action')}
                <ArrowRight size={16} />
              </Link>
              <Link
                to="/projekte"
                className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
              >
                {t('landing.hero.secondary_action')}
              </Link>
            </div>
          }
        />

        <div className="mt-10 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
          <div className="rounded-[1.75rem] border border-[color:var(--color-line)] bg-white/80 p-6">
            <StatusBadge tone="accent">{t('landing.highlights.eyebrow')}</StatusBadge>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-[color:var(--color-ink)]">
              {t('landing.highlights.body')}
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t('landing.metrics.projects_label')}
                </p>
                <p className="mt-2 text-3xl font-semibold tracking-[-0.04em]">{t('landing.metrics.projects_value')}</p>
              </div>
              <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t('landing.metrics.workflow_label')}
                </p>
                <p className="mt-2 text-3xl font-semibold tracking-[-0.04em]">{t('landing.metrics.workflow_value')}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="rounded-[1.75rem] border border-[color:var(--color-line)] bg-[color:var(--color-ink)] p-6 text-white">
              <DraftingCompass size={30} className="text-white/80" />
              <h2 className="mt-6 text-2xl font-semibold tracking-[-0.04em]">
                {t('landing.cards.create.title')}
              </h2>
              <p className="mt-3 text-sm leading-7 text-white/72">{t('landing.cards.create.description')}</p>
            </div>

            <div className="rounded-[1.75rem] border border-[color:var(--color-line)] bg-white/80 p-6">
              <FolderKanban size={26} className="text-[color:var(--color-accent)]" />
              <h2 className="mt-5 text-2xl font-semibold tracking-[-0.04em]">
                {t('landing.cards.list.title')}
              </h2>
              <p className="mt-3 text-sm leading-7 text-[color:var(--color-mist)]">
                {t('landing.cards.list.description')}
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}