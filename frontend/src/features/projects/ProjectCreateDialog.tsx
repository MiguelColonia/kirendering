import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { createProject } from '../../api/projects'
import { createProjectSeedPayload } from './projectDefaults'

type ProjectCreateDialogProps = {
  isOpen: boolean
  onClose: () => void
}

function inputClasses() {
  return 'mt-2 w-full rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-accent)]'
}

export function ProjectCreateDialog({ isOpen, onClose }: ProjectCreateDialogProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [projectName, setProjectName] = useState('')
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!isOpen) {
      setProjectName('')
      setDescription('')
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) {
      return undefined
    }

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeydown)
    return () => {
      window.removeEventListener('keydown', handleKeydown)
    }
  }, [isOpen, onClose])

  const createMutation = useMutation({
    mutationFn: async () => createProject(createProjectSeedPayload(projectName, description)),
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.setQueryData(['project', project.id], project)
      navigate(`/projekte/${project.id}`)
    },
  })

  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[color:var(--color-ink)]/28 px-4 py-8 backdrop-blur-sm">
      <div className="panel-surface w-full max-w-2xl rounded-[2rem] p-6 md:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--color-accent)]">
              {t('project_create.eyebrow')}
            </p>
            <div>
              <h2 className="text-3xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
                {t('project_create.title')}
              </h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-[color:var(--color-mist)]">
                {t('project_create.description')}
              </p>
            </div>
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

        <div className="mt-6 grid gap-4">
          <label className="text-sm font-medium text-[color:var(--color-ink)]">
            {t('project_create.fields.name')}
            <input
              autoFocus
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              className={inputClasses()}
            />
          </label>

          <label className="text-sm font-medium text-[color:var(--color-ink)]">
            {t('project_create.fields.description')}
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              className={inputClasses()}
            />
          </label>
        </div>

        {createMutation.isError ? (
          <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {t('project_create.error')}
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[color:var(--color-line)] px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || projectName.trim().length === 0}
            className="rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#143f50] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t('project_create.submit')}
          </button>
        </div>
      </div>
    </div>
  )
}