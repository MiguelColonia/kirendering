import { useEffect, useRef } from 'react'
import { buildJobStreamUrl } from '../api/projects'
import type { JobEvent } from '../types/project'

type EventHandler = (event: JobEvent) => void

export function useJobStream(jobId: string | null, onEvent: EventHandler): void {
  const handlerRef = useRef(onEvent)

  useEffect(() => {
    handlerRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!jobId) {
      return undefined
    }

    const socket = new WebSocket(buildJobStreamUrl(jobId))
    socket.onmessage = (message) => {
      const payload = JSON.parse(message.data) as JobEvent | { error: { code: string; message: string } }
      if ('event' in payload) {
        handlerRef.current(payload)
      }
    }

    return () => {
      socket.close()
    }
  }, [jobId])
}