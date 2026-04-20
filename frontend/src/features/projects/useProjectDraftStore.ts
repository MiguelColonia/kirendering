import { create } from 'zustand'
import type { Program, ProjectDetail, Solar } from '../../types/project'
import { createDefaultProgram, createDefaultSolar } from './projectDefaults'

type DraftState = {
  projectName: string
  description: string
  solar: Solar
  program: Program
  resetDraft: () => void
  hydrateFromProject: (project: ProjectDetail) => void
  setProjectMeta: (field: 'projectName' | 'description', value: string) => void
  setSolarPoints: (points: Solar['contour']['points']) => void
  updateProgram: (program: Program) => void
}

const initialState = {
  projectName: 'Mehrfamilienhaus Nordhof',
  description: 'Vier Geschosse, kompaktes Treppenhaus und vorbereitetes Tiefgaragenkonzept.',
  solar: createDefaultSolar(),
  program: createDefaultProgram(),
}

export const useProjectDraftStore = create<DraftState>((set) => ({
  ...initialState,
  resetDraft: () =>
    set({
      ...initialState,
      solar: createDefaultSolar(),
      program: createDefaultProgram(),
    }),
  hydrateFromProject: (project) =>
    set({
      projectName: project.name,
      description: project.description ?? '',
      solar: project.current_version?.solar ?? createDefaultSolar(),
      program: project.current_version?.program ?? createDefaultProgram(),
    }),
  setProjectMeta: (field, value) =>
    set((state) => ({
      ...state,
      [field]: value,
    })),
  setSolarPoints: (points) =>
    set((state) => ({
      solar: {
        ...state.solar,
        contour: {
          points,
        },
      },
    })),
  updateProgram: (program) => set({ program }),
}))