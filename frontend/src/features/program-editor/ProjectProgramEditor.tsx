import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Save, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { updateProject } from '../../api/projects'
import { StatusBadge } from '../../components/StatusBadge'
import type { Program, ProjectDetail, Typology } from '../../types/project'
import { createDefaultProgram, createDefaultSolar } from '../projects/projectDefaults'
import {
  createEmptyTypology,
  createProgramSchema,
  mapZodIssues,
  synchronizeMix,
} from './programValidation'
import { TypologyDialog } from './TypologyDialog'

type ProgramSubview = 'typologies' | 'mix'

type ProjectProgramEditorProps = {
  project: ProjectDetail
}

function numberInputClasses() {
  return 'mt-2 w-full rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-accent)]'
}

export function ProjectProgramEditor({ project }: ProjectProgramEditorProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [activeSubview, setActiveSubview] = useState<ProgramSubview>('typologies')
  const [draftProgram, setDraftProgram] = useState<Program>(
    project.current_version?.program ?? createDefaultProgram(),
  )
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingTypology, setEditingTypology] = useState<Typology | null>(null)
  const [formMessage, setFormMessage] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const programSchema = useMemo(() => createProgramSchema(t), [t])

  useEffect(() => {
    setDraftProgram(project.current_version?.program ?? createDefaultProgram())
    setFormMessage(null)
    setFormError(null)
  }, [project.current_version?.id, project.current_version?.updated_at, project.id])

  const saveMutation = useMutation({
    mutationFn: async () => {
      const normalizedProgram = synchronizeMix(draftProgram)
      const result = programSchema.safeParse(normalizedProgram)
      if (!result.success) {
        const issues = mapZodIssues(result.error)
        throw new Error(issues.root ?? Object.values(issues)[0] ?? t('program_editor.save_error'))
      }

      return updateProject(project.id, {
        name: project.name,
        description: project.description,
        solar: project.current_version?.solar ?? createDefaultSolar(),
        program: result.data,
      })
    },
    onSuccess: (updatedProject) => {
      queryClient.setQueryData(['project', project.id], updatedProject)
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      setDraftProgram(updatedProject.current_version?.program ?? createDefaultProgram())
      setFormError(null)
      setFormMessage(t('program_editor.save_success'))
    },
    onError: (error) => {
      setFormMessage(null)
      setFormError(error instanceof Error ? error.message : t('program_editor.save_error'))
    },
  })

  const synchronizedProgram = synchronizeMix(draftProgram)
  const totalUnits = synchronizedProgram.mix.reduce((total, entry) => total + entry.count, 0)

  const upsertTypology = (nextTypology: Typology, previousId?: string) => {
    const nextTypologies = synchronizedProgram.typologies.some((entry) => entry.id === previousId)
      ? synchronizedProgram.typologies.map((entry) =>
          entry.id === previousId ? nextTypology : entry,
        )
      : [...synchronizedProgram.typologies, nextTypology]

    const previousCount = synchronizedProgram.mix.find(
      (entry) => entry.typology_id === previousId,
    )?.count

    const normalized = synchronizeMix({
      ...synchronizedProgram,
      typologies: nextTypologies,
      mix: synchronizedProgram.mix.map((entry) =>
        entry.typology_id === previousId ? { ...entry, typology_id: nextTypology.id } : entry,
      ),
    })

    setDraftProgram({
      ...normalized,
      mix: normalized.mix.map((entry) =>
        entry.typology_id === nextTypology.id
          ? { ...entry, count: previousCount ?? entry.count }
          : entry,
      ),
    })
    setFormMessage(null)
    setFormError(null)
  }

  const removeTypology = (typologyId: string) => {
    setDraftProgram(
      synchronizeMix({
        ...synchronizedProgram,
        typologies: synchronizedProgram.typologies.filter((entry) => entry.id !== typologyId),
        mix: synchronizedProgram.mix.filter((entry) => entry.typology_id !== typologyId),
      }),
    )
    setFormMessage(null)
    setFormError(null)
  }

  return (
    <section className="panel-surface rounded-[2rem] p-6 md:p-8">
      <div className="flex flex-col gap-5 border-b border-[color:var(--color-line)] pb-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <StatusBadge tone="accent">{t('project_editor.tabs.program')}</StatusBadge>
          <div>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {t('program_editor.title')}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-[color:var(--color-mist)]">
              {t('program_editor.description')}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              setEditingTypology(createEmptyTypology())
              setDialogOpen(true)
            }}
            className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/85 px-4 py-3 text-sm font-semibold text-[color:var(--color-accent)]"
          >
            <Plus size={16} />
            {t('program_editor.actions.add_typology')}
          </button>
          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#143f50] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Save size={16} />
            {t('program_editor.actions.save_program')}
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-4">
        <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
            {t('program_editor.summary.typologies')}
          </p>
          <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
            {synchronizedProgram.typologies.length}
          </p>
        </div>
        <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
            {t('program_editor.summary.units')}
          </p>
          <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
            {totalUnits}
          </p>
        </div>
        <label className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4 text-sm font-medium text-[color:var(--color-ink)]">
          {t('program_editor.summary.floors')}
          <input
            type="number"
            min={1}
            value={draftProgram.num_floors}
            onChange={(event) =>
              setDraftProgram({
                ...draftProgram,
                num_floors: Math.max(1, Number(event.target.value)),
              })
            }
            className={numberInputClasses()}
          />
        </label>
        <label className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4 text-sm font-medium text-[color:var(--color-ink)]">
          {t('program_editor.summary.floor_height')}
          <input
            type="number"
            min={0.1}
            step={0.1}
            value={draftProgram.floor_height_m}
            onChange={(event) =>
              setDraftProgram({
                ...draftProgram,
                floor_height_m: Math.max(0.1, Number(event.target.value)),
              })
            }
            className={numberInputClasses()}
          />
        </label>
      </div>

      <div className="mt-6 flex flex-wrap gap-3 border-b border-[color:var(--color-line)] pb-5">
        {(['typologies', 'mix'] as ProgramSubview[]).map((view) => (
          <button
            key={view}
            type="button"
            onClick={() => setActiveSubview(view)}
            className={[
              'rounded-full border px-4 py-2 text-sm font-semibold transition',
              activeSubview === view
                ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]'
                : 'border-[color:var(--color-line)] bg-white/70 text-[color:var(--color-mist)] hover:text-[color:var(--color-ink)]',
            ].join(' ')}
          >
            {t(`program_editor.subviews.${view}`)}
          </button>
        ))}
      </div>

      {formMessage ? (
        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {formMessage}
        </div>
      ) : null}

      {formError ? (
        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {formError}
        </div>
      ) : null}

      {activeSubview === 'typologies' ? (
        <div className="mt-6 space-y-4">
          {synchronizedProgram.typologies.length === 0 ? (
            <div className="rounded-[1.5rem] border border-dashed border-[color:var(--color-line)] px-5 py-8 text-sm text-[color:var(--color-mist)]">
              {t('program_editor.typology_list.empty')}
            </div>
          ) : null}

          {synchronizedProgram.typologies.map((typology) => (
            <article
              key={typology.id}
              className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/82 p-5"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                      {typology.name || t('program_editor.typology_list.untitled')}
                    </h3>
                    <StatusBadge>{typology.id || 'ID'}</StatusBadge>
                  </div>

                  <div className="flex flex-wrap gap-4 text-sm text-[color:var(--color-mist)]">
                    <span>
                      {t('program_editor.typology_list.bedrooms', { count: typology.num_bedrooms })}
                    </span>
                    <span>
                      {t('program_editor.typology_list.bathrooms', { count: typology.num_bathrooms })}
                    </span>
                    <span>
                      {t('program_editor.typology_list.area_range', {
                        min: typology.min_useful_area,
                        max: typology.max_useful_area,
                      })}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {typology.rooms.map((room, index) => (
                      <span
                        key={`${typology.id}-${room.type}-${index}`}
                        className="rounded-full border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-3 py-1 text-xs font-medium text-[color:var(--color-mist)]"
                      >
                        {t(`room_types.${room.type}`)}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingTypology(typology)
                      setDialogOpen(true)
                    }}
                    className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] px-4 py-2 text-sm font-semibold text-[color:var(--color-ink)]"
                  >
                    <Pencil size={16} />
                    {t('program_editor.actions.edit_typology')}
                  </button>
                  <button
                    type="button"
                    onClick={() => removeTypology(typology.id)}
                    className="inline-flex items-center gap-2 rounded-full border border-amber-200 px-4 py-2 text-sm font-semibold text-amber-700"
                  >
                    <Trash2 size={16} />
                    {t('program_editor.actions.delete_typology')}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {activeSubview === 'mix' ? (
        <div className="mt-6 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/82">
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead className="bg-[color:var(--color-paper)]/95">
                <tr>
                  <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t('program_editor.mix.columns.typology')}
                  </th>
                  <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t('program_editor.mix.columns.id')}
                  </th>
                  <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t('program_editor.mix.columns.count')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {synchronizedProgram.mix.map((entry) => {
                  const typology = synchronizedProgram.typologies.find(
                    (item) => item.id === entry.typology_id,
                  )

                  return (
                    <tr key={entry.typology_id} className="border-t border-[color:var(--color-line)]">
                      <td className="px-5 py-4 text-sm font-medium text-[color:var(--color-ink)]">
                        {typology?.name || t('program_editor.typology_list.untitled')}
                      </td>
                      <td className="px-5 py-4 text-sm text-[color:var(--color-mist)]">{entry.typology_id}</td>
                      <td className="px-5 py-4">
                        <input
                          type="number"
                          min={1}
                          value={entry.count}
                          onChange={(event) => {
                            const nextCount = Math.max(1, Number(event.target.value))
                            setDraftProgram({
                              ...draftProgram,
                              mix: synchronizedProgram.mix.map((mixEntry) =>
                                mixEntry.typology_id === entry.typology_id
                                  ? { ...mixEntry, count: nextCount }
                                  : mixEntry,
                              ),
                            })
                            setFormMessage(null)
                            setFormError(null)
                          }}
                          className="w-28 rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-accent)]"
                        />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="border-t border-[color:var(--color-line)] bg-[color:var(--color-paper)]/80 px-5 py-4 text-sm font-semibold text-[color:var(--color-ink)]">
            {t('program_editor.mix.total_units', { count: totalUnits })}
          </div>
        </div>
      ) : null}

      <TypologyDialog
        isOpen={dialogOpen}
        existingIds={synchronizedProgram.typologies.map((entry) => entry.id).filter(Boolean)}
        initialValue={editingTypology}
        onClose={() => setDialogOpen(false)}
        onSubmit={upsertTypology}
      />
    </section>
  )
}