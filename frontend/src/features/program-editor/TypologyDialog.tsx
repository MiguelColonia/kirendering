import { useEffect, useMemo, useState } from 'react'
import { MinusCircle, PlusCircle, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Room, Typology } from '../../types/project'
import {
  createEmptyRoom,
  createEmptyTypology,
  createTypologySchema,
  mapZodIssues,
  ROOM_TYPE_VALUES,
  type FieldErrors,
} from './programValidation'

type TypologyDialogProps = {
  isOpen: boolean
  existingIds: string[]
  initialValue?: Typology | null
  onClose: () => void
  onSubmit: (typology: Typology, previousId?: string) => void
}

function inputClasses(hasError: boolean) {
  return [
    'mt-2 w-full rounded-2xl border bg-white px-4 py-3 text-sm outline-none transition',
    hasError
      ? 'border-amber-300 bg-amber-50/70 focus:border-amber-400'
      : 'border-[color:var(--color-line)] focus:border-[color:var(--color-accent)]',
  ].join(' ')
}

export function TypologyDialog({
  isOpen,
  existingIds,
  initialValue,
  onClose,
  onSubmit,
}: TypologyDialogProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<Typology>(initialValue ?? createEmptyTypology())
  const [errors, setErrors] = useState<FieldErrors>({})
  const previousId = initialValue?.id

  const schema = useMemo(
    () => createTypologySchema(t, existingIds, previousId),
    [existingIds, previousId, t],
  )

  useEffect(() => {
    if (isOpen) {
      setDraft(initialValue ?? createEmptyTypology())
      setErrors({})
    }
  }, [initialValue, isOpen])

  if (!isOpen) {
    return null
  }

  const submit = () => {
    const result = schema.safeParse(draft)
    if (!result.success) {
      setErrors(mapZodIssues(result.error))
      return
    }

    onSubmit(result.data, previousId)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[color:var(--color-ink)]/30 px-4 py-8 backdrop-blur-sm">
      <div className="panel-surface w-full max-w-5xl rounded-[2rem] p-6 md:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--color-accent)]">
              {t('program_editor.typology_dialog.eyebrow')}
            </p>
            <h2 className="text-3xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {initialValue
                ? t('program_editor.typology_dialog.edit_title')
                : t('program_editor.typology_dialog.create_title')}
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[color:var(--color-line)] p-2 text-[color:var(--color-mist)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)]"
            aria-label={t('common.close')}
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
          <section className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/70 p-5">
            <h3 className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
              {t('program_editor.typology_dialog.sections.basics')}
            </h3>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium text-[color:var(--color-ink)]">
                {t('program_editor.typology_dialog.fields.name')}
                <input
                  value={draft.name}
                  onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                  className={inputClasses(Boolean(errors.name))}
                />
                {errors.name ? <p className="mt-2 text-xs text-amber-700">{errors.name}</p> : null}
              </label>

              <label className="text-sm font-medium text-[color:var(--color-ink)]">
                {t('program_editor.typology_dialog.fields.id')}
                <input
                  value={draft.id}
                  onChange={(event) => setDraft({ ...draft, id: event.target.value })}
                  className={inputClasses(Boolean(errors.id))}
                />
                {errors.id ? <p className="mt-2 text-xs text-amber-700">{errors.id}</p> : null}
              </label>

              <label className="text-sm font-medium text-[color:var(--color-ink)]">
                {t('program_editor.typology_dialog.fields.bedrooms')}
                <input
                  type="number"
                  min={0}
                  value={draft.num_bedrooms}
                  onChange={(event) =>
                    setDraft({ ...draft, num_bedrooms: Number(event.target.value) })
                  }
                  className={inputClasses(Boolean(errors.num_bedrooms))}
                />
                {errors.num_bedrooms ? (
                  <p className="mt-2 text-xs text-amber-700">{errors.num_bedrooms}</p>
                ) : null}
              </label>

              <label className="text-sm font-medium text-[color:var(--color-ink)]">
                {t('program_editor.typology_dialog.fields.bathrooms')}
                <input
                  type="number"
                  min={1}
                  value={draft.num_bathrooms}
                  onChange={(event) =>
                    setDraft({ ...draft, num_bathrooms: Number(event.target.value) })
                  }
                  className={inputClasses(Boolean(errors.num_bathrooms))}
                />
                {errors.num_bathrooms ? (
                  <p className="mt-2 text-xs text-amber-700">{errors.num_bathrooms}</p>
                ) : null}
              </label>
            </div>

            <h3 className="mt-6 text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
              {t('program_editor.typology_dialog.sections.areas')}
            </h3>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium text-[color:var(--color-ink)]">
                {t('program_editor.typology_dialog.fields.min_area')}
                <input
                  type="number"
                  min={1}
                  step={0.5}
                  value={draft.min_useful_area}
                  onChange={(event) =>
                    setDraft({ ...draft, min_useful_area: Number(event.target.value) })
                  }
                  className={inputClasses(Boolean(errors.min_useful_area))}
                />
                {errors.min_useful_area ? (
                  <p className="mt-2 text-xs text-amber-700">{errors.min_useful_area}</p>
                ) : null}
              </label>

              <label className="text-sm font-medium text-[color:var(--color-ink)]">
                {t('program_editor.typology_dialog.fields.max_area')}
                <input
                  type="number"
                  min={1}
                  step={0.5}
                  value={draft.max_useful_area}
                  onChange={(event) =>
                    setDraft({ ...draft, max_useful_area: Number(event.target.value) })
                  }
                  className={inputClasses(Boolean(errors.max_useful_area))}
                />
                {errors.max_useful_area ? (
                  <p className="mt-2 text-xs text-amber-700">{errors.max_useful_area}</p>
                ) : null}
              </label>
            </div>
          </section>

          <section className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/70 p-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {t('program_editor.typology_dialog.sections.rooms')}
                </h3>
                {errors.rooms ? <p className="mt-2 text-xs text-amber-700">{errors.rooms}</p> : null}
              </div>
              <button
                type="button"
                onClick={() => setDraft({ ...draft, rooms: [...draft.rooms, createEmptyRoom()] })}
                className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] px-4 py-2 text-sm font-semibold text-[color:var(--color-accent)]"
              >
                <PlusCircle size={16} />
                {t('program_editor.typology_dialog.add_room')}
              </button>
            </div>

            <div className="mt-4 space-y-4">
              {draft.rooms.map((room, index) => (
                <div key={`${room.type}-${index}`} className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] p-4">
                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_repeat(2,minmax(0,0.8fr))_auto]">
                    <label className="text-sm font-medium text-[color:var(--color-ink)]">
                      {t('program_editor.typology_dialog.fields.room_type')}
                      <select
                        value={room.type}
                        onChange={(event) => {
                          const nextRooms = [...draft.rooms]
                          nextRooms[index] = { ...room, type: event.target.value as Room['type'] }
                          setDraft({ ...draft, rooms: nextRooms })
                        }}
                        className={inputClasses(Boolean(errors[`rooms.${index}.type`]))}
                      >
                        {ROOM_TYPE_VALUES.map((roomType) => (
                          <option key={roomType} value={roomType}>
                            {t(`room_types.${roomType}`)}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="text-sm font-medium text-[color:var(--color-ink)]">
                      {t('program_editor.typology_dialog.fields.room_min_area')}
                      <input
                        type="number"
                        min={0.5}
                        step={0.5}
                        value={room.min_area}
                        onChange={(event) => {
                          const nextRooms = [...draft.rooms]
                          nextRooms[index] = { ...room, min_area: Number(event.target.value) }
                          setDraft({ ...draft, rooms: nextRooms })
                        }}
                        className={inputClasses(Boolean(errors[`rooms.${index}.min_area`]))}
                      />
                    </label>

                    <label className="text-sm font-medium text-[color:var(--color-ink)]">
                      {t('program_editor.typology_dialog.fields.room_min_short_side')}
                      <input
                        type="number"
                        min={0.5}
                        step={0.1}
                        value={room.min_short_side}
                        onChange={(event) => {
                          const nextRooms = [...draft.rooms]
                          nextRooms[index] = {
                            ...room,
                            min_short_side: Number(event.target.value),
                          }
                          setDraft({ ...draft, rooms: nextRooms })
                        }}
                        className={inputClasses(Boolean(errors[`rooms.${index}.min_short_side`]))}
                      />
                    </label>

                    <div className="flex items-end">
                      <button
                        type="button"
                        onClick={() => {
                          setDraft({
                            ...draft,
                            rooms: draft.rooms.filter((_, roomIndex) => roomIndex !== index),
                          })
                        }}
                        className="inline-flex items-center gap-2 rounded-full border border-amber-200 px-4 py-3 text-sm font-semibold text-amber-700"
                      >
                        <MinusCircle size={16} />
                        {t('program_editor.typology_dialog.remove_room')}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[color:var(--color-line)] px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            className="rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#143f50]"
          >
            {t('program_editor.typology_dialog.submit')}
          </button>
        </div>
      </div>
    </div>
  )
}