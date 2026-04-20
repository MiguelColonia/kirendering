import { useEffect, useRef } from "react";
import { buildJobStreamUrl } from "../api/projects";
import type { JobEvent } from "../types/project";

type EventHandler = (event: JobEvent) => void;

export type JobStreamError = {
  code?: string;
  message: string;
};

export type JobStreamCloseReason = "completed" | "not_found";

type JobStreamHandlers = {
  onEvent: EventHandler;
  onOpen?: () => void;
  onReconnect?: (attempt: number) => void;
  onSocketError?: (error: JobStreamError) => void;
  onClose?: (reason: JobStreamCloseReason) => void;
};

function normalizeHandlers(
  handlersOrOnEvent: EventHandler | JobStreamHandlers,
): JobStreamHandlers {
  return typeof handlersOrOnEvent === "function"
    ? { onEvent: handlersOrOnEvent }
    : handlersOrOnEvent;
}

export function useJobStream(
  jobId: string | null,
  handlersOrOnEvent: EventHandler | JobStreamHandlers,
): void {
  const handlersRef = useRef<JobStreamHandlers>(
    normalizeHandlers(handlersOrOnEvent),
  );

  useEffect(() => {
    handlersRef.current = normalizeHandlers(handlersOrOnEvent);
  }, [handlersOrOnEvent]);

  useEffect(() => {
    if (!jobId) {
      return undefined;
    }

    let disposed = false;
    let reconnectAttempt = 0;
    let reconnectTimer: number | undefined;
    let terminalEventSeen = false;
    let activeSocket: WebSocket | null = null;

    const connect = () => {
      if (disposed) {
        return;
      }

      const socket = new WebSocket(buildJobStreamUrl(jobId));
      activeSocket = socket;

      socket.onopen = () => {
        reconnectAttempt = 0;
        handlersRef.current.onOpen?.();
      };

      socket.onmessage = (message) => {
        let payload: JobEvent | { error: { code: string; message: string } };

        try {
          payload = JSON.parse(message.data) as
            | JobEvent
            | { error: { code: string; message: string } };
        } catch {
          handlersRef.current.onSocketError?.({
            message: "Ungültige Antwort vom Live-Stream.",
          });
          return;
        }

        if ("event" in payload) {
          handlersRef.current.onEvent(payload);
          if (payload.event === "finished" || payload.event === "failed") {
            terminalEventSeen = true;
          }
          return;
        }

        handlersRef.current.onSocketError?.({
          code: payload.error.code,
          message: payload.error.message,
        });

        if (payload.error.code === "JOB_NOT_FOUND") {
          terminalEventSeen = true;
          socket.close(4404, payload.error.message);
        }
      };

      socket.onerror = () => {
        if (disposed || terminalEventSeen) {
          return;
        }

        handlersRef.current.onSocketError?.({
          message:
            "Die Live-Verbindung zur Generierung ist derzeit nicht verfügbar.",
        });
      };

      socket.onclose = (event) => {
        if (disposed) {
          return;
        }

        if (terminalEventSeen) {
          handlersRef.current.onClose?.(
            event.code === 4404 ? "not_found" : "completed",
          );
          return;
        }

        reconnectAttempt += 1;
        handlersRef.current.onReconnect?.(reconnectAttempt);

        const delay = Math.min(1000 * 2 ** (reconnectAttempt - 1), 8000);
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      disposed = true;
      terminalEventSeen = true;
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer);
      }
      activeSocket?.close();
    };
  }, [jobId]);
}
