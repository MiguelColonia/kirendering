import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useReducer } from 'react'
import { useTranslation } from 'react-i18next'
import { generateProject } from '../../api/projects'
import { GenerationStatusPanel } from './GenerationStatusPanel'
import { useJobStream, type JobStreamCloseReason, type JobStreamError } from '../../hooks/useJobStream'
import type { JobEvent } from '../../types/project'

type GenerationConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'closed'
  | 'error'

type GenerationState = {
  jobId: string | null
  status: string
  events: JobEvent[]
  startError: string | null
  connectionStatus: GenerationConnectionStatus
  connectionError: string | null
}

type GenerationAction =
  | { type: 'job-started'; jobId: string; status: string }
  | { type: 'job-start-failed'; message: string }
  | { type: 'socket-open' }
  | { type: 'socket-reconnecting'; message: string }
  | { type: 'socket-error'; message: string }
  | { type: 'socket-closed'; reason: JobStreamCloseReason }
  | { type: 'event-received'; event: JobEvent }

const initialGenerationState: GenerationState = {
  jobId: null,
  status: 'idle',
  events: [],
  startError: null,
  connectionStatus: 'idle',
  connectionError: null,
}

function makeEventKey(event: JobEvent): string {
  return `${event.timestamp}:${event.event}:${JSON.stringify(event.data)}`
}

function generationReducer(
  state: GenerationState,
  action: GenerationAction,
): GenerationState {
  switch (action.type) {
    case 'job-started':
      return {
        jobId: action.jobId,
        status: action.status,
        events: [],
        startError: null,
        connectionStatus: 'connecting',
        connectionError: null,
      }
    case 'job-start-failed':
      return {
        ...initialGenerationState,
        startError: action.message,
      }
    case 'socket-open':
      return {
        ...state,
        connectionStatus: 'connected',
        connectionError: null,
      }
    case 'socket-reconnecting':
      return {
        ...state,
        connectionStatus: 'reconnecting',
        connectionError: action.message,
      }
    case 'socket-error':
      return {
        ...state,
        connectionStatus: state.connectionStatus === 'reconnecting' ? 'reconnecting' : 'error',
        connectionError: action.message,
      }
    case 'socket-closed':
      return {
        ...state,
        connectionStatus: action.reason === 'completed' ? 'closed' : 'error',
      }
    case 'event-received': {
      const eventExists = state.events.some(
        (currentEvent) => makeEventKey(currentEvent) === makeEventKey(action.event),
      )
      if (eventExists) {
        return state
      }

      const nextEvents = [...state.events, action.event].sort((left, right) => {
        return Date.parse(left.timestamp) - Date.parse(right.timestamp)
      })

      if (action.event.event === 'finished') {
        return {
          ...state,
          events: nextEvents,
          status: 'finished',
          connectionError: null,
        }
      }

      if (action.event.event === 'failed') {
        return {
          ...state,
          events: nextEvents,
          status: 'failed',
        }
      }

      return {
        ...state,
        events: nextEvents,
        status: 'running',
      }
    }
    default:
      return state
  }
}

function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as { error?: { message?: string } } | undefined
    if (payload?.error?.message) {
      return payload.error.message
    }

    if (error.code === 'ECONNABORTED') {
      return fallback
    }
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

type ProjectGenerationPanelProps = {
  projectId: string
}

export function ProjectGenerationPanel({ projectId }: ProjectGenerationPanelProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [state, dispatch] = useReducer(generationReducer, initialGenerationState)

  const refreshProject = () => {
    void queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    void queryClient.invalidateQueries({ queryKey: ['projects'] })
  }

  const handleSocketError = (error: JobStreamError) => {
    dispatch({ type: 'socket-error', message: error.message })
  }

  useJobStream(state.jobId, {
    onEvent: (event) => {
      dispatch({ type: 'event-received', event })

      if (event.event === 'finished' || event.event === 'failed') {
        refreshProject()
      }
    },
    onOpen: () => {
      dispatch({ type: 'socket-open' })
    },
    onReconnect: () => {
      dispatch({
        type: 'socket-reconnecting',
        message: t('generation.connection_lost'),
      })
    },
    onSocketError: handleSocketError,
    onClose: (reason) => {
      dispatch({ type: 'socket-closed', reason })
    },
  })

  const generateMutation = useMutation({
    mutationFn: async () => generateProject(projectId),
    onSuccess: ({ job_id, status }) => {
      dispatch({ type: 'job-started', jobId: job_id, status })
    },
    onError: (error) => {
      dispatch({
        type: 'job-start-failed',
        message: extractApiErrorMessage(error, t('generation.start_error')),
      })
    },
  })

  const isGenerating =
    generateMutation.isPending ||
    state.status === 'queued' ||
    state.status === 'running' ||
    state.connectionStatus === 'connecting' ||
    state.connectionStatus === 'reconnecting'

  return (
    <GenerationStatusPanel
      jobId={state.jobId}
      status={generateMutation.isPending ? 'queued' : state.status}
      events={state.events}
      isPending={isGenerating}
      onGenerate={() => generateMutation.mutate()}
      startError={state.startError}
      connectionStatus={state.connectionStatus}
      connectionError={state.connectionError}
    />
  )
}