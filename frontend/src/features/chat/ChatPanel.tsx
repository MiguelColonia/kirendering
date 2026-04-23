/**
 * ChatPanel — panel lateral de conversación con el copiloto IA de Cimiento.
 *
 * Protocolo WebSocket (backend → frontend):
 *   { type: "node_start",  node: string, label: string }  — un nodo del grafo LangGraph se activa
 *   { type: "node_end",    node: string }                  — el nodo terminó
 *   { type: "done",        response: string, feasible: bool, solution: object | null }
 *   { type: "error",       message: string }
 *
 * El WS se crea de nuevo en cada envío de mensaje y se cierra al recibir "done" o "error".
 * No se mantiene una conexión persistente para simplificar el manejo de reconexiones.
 *
 * El historial de mensajes vive solo en memoria del componente; se pierde al navegar.
 * (Ver ROADMAP para persistencia durable del chat — trabajo abierto para v1.x.)
 */
import { useEffect, useRef, useState } from "react";
import { MessageSquare, ChevronRight, Send } from "lucide-react";
import { buildChatStreamUrl } from "../../api/projects";
import type { ChatMessage, ChatStreamEvent } from "../../types/project";

const NODE_LABELS: Record<string, string> = {
  extract_requirements: "Anforderungen werden analysiert…",
  validate_normative: "Normvorschriften werden geprüft…",
  invoke_solver: "Solver läuft…",
  interpret_result: "Antwort wird generiert…",
  handle_infeasible: "Anpassungsvorschläge werden erstellt…",
};

function createThreadId(projectId: string): string {
  const suffix = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`;
  return `${projectId}-${suffix}`;
}

interface Props {
  projectId: string;
}

export function ChatPanel({ projectId }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [activeNodeLabel, setActiveNodeLabel] = useState<string | null>(null);
  const [isThinking, setIsThinking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadIdRef = useRef(createThreadId(projectId));
  const currentProjectIdRef = useRef(projectId);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, activeNodeLabel]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  useEffect(() => {
    if (currentProjectIdRef.current === projectId) {
      return;
    }

    currentProjectIdRef.current = projectId;
    wsRef.current?.close();
    wsRef.current = null;
    threadIdRef.current = createThreadId(projectId);
    setMessages([]);
    setInput("");
    setActiveNodeLabel(null);
    setIsThinking(false);
  }, [projectId]);

  const openPanel = () => {
    setIsOpen(true);
    setTimeout(() => inputRef.current?.focus(), 150);
  };

  const sendMessage = () => {
    const text = input.trim();
    if (!text || isThinking) return;

    wsRef.current?.close();
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setIsThinking(true);
    setActiveNodeLabel("Verbindung wird hergestellt…");

    const ws = new WebSocket(buildChatStreamUrl(projectId));
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({ message: text, thread_id: threadIdRef.current }),
      );
      setActiveNodeLabel("Assistent denkt nach…");
    };

    ws.onmessage = (e: MessageEvent<string>) => {
      let event: ChatStreamEvent;
      try {
        event = JSON.parse(e.data) as ChatStreamEvent;
      } catch {
        return;
      }

      if (event.type === "node_start") {
        setActiveNodeLabel(
          event.label ?? NODE_LABELS[event.node] ?? event.node,
        );
      } else if (event.type === "node_end") {
        setActiveNodeLabel(null);
      } else if (event.type === "done") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: event.response,
            feasible: event.feasible,
            solution: event.solution,
          },
        ]);
        setIsThinking(false);
        setActiveNodeLabel(null);
      } else if (event.type === "error") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Fehler: ${event.message}` },
        ]);
        setIsThinking(false);
        setActiveNodeLabel(null);
      }
    };

    ws.onerror = () => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Verbindungsfehler. Bitte versuchen Sie es erneut.",
        },
      ]);
      setIsThinking(false);
      setActiveNodeLabel(null);
    };
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {!isOpen && (
        <button
          type="button"
          onClick={openPanel}
          className="fixed right-0 top-1/2 z-40 flex -translate-y-1/2 flex-col items-center gap-2 rounded-l-2xl bg-[color:var(--color-clay)] px-3 py-4 text-white shadow-lg transition-colors hover:opacity-90"
          aria-label="KI-Assistent öffnen"
        >
          <MessageSquare size={20} />
          <span className="text-xs font-semibold tracking-wider [writing-mode:vertical-rl]">
            KI-Assistent
          </span>
        </button>
      )}

      <div
        className={`fixed right-0 top-0 z-50 flex h-full w-[420px] flex-col bg-[color:var(--color-paper)] shadow-2xl transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
        aria-hidden={!isOpen}
      >
        <div className="flex items-center justify-between border-b border-[color:var(--color-line)] bg-white/80 px-5 py-4">
          <div className="flex items-center gap-2">
            <MessageSquare
              size={18}
              className="text-[color:var(--color-clay)]"
            />
            <h2 className="text-base font-semibold tracking-[-0.02em]">
              KI-Assistent
            </h2>
          </div>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="rounded-full p-1.5 text-[color:var(--color-mist)] transition-colors hover:bg-[color:var(--color-sand)] hover:text-[color:var(--color-ink)]"
            aria-label="Panel schließen"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        <div
          ref={scrollRef}
          className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
        >
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-4 px-8">
              <p className="text-center text-sm text-[color:var(--color-mist)]">
                Stellen Sie eine Frage zu Ihrem Projekt — z.&nbsp;B. zur
                Grundrissoptimierung oder zu Normvorschriften.
              </p>
              <p className="text-center text-xs text-[color:var(--color-mist)] opacity-60">
                Der Gesprächsverlauf wird beim Seitenwechsel nicht gespeichert.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "rounded-br-sm bg-[color:var(--color-clay)] text-white"
                    : "rounded-bl-sm border border-[color:var(--color-line)] bg-white/90 text-[color:var(--color-ink)]"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.role === "assistant" && msg.feasible !== undefined && (
                  <span
                    className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      msg.feasible
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {msg.feasible ? "Machbar" : "Nicht machbar"}
                  </span>
                )}
              </div>
            </div>
          ))}

          {isThinking && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-[color:var(--color-line)] bg-white/90 px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[color:var(--color-mist)] [animation-delay:0ms]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[color:var(--color-mist)] [animation-delay:150ms]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[color:var(--color-mist)] [animation-delay:300ms]" />
                  </span>
                  {activeNodeLabel && (
                    <span className="text-xs text-[color:var(--color-mist)]">
                      {activeNodeLabel}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-[color:var(--color-line)] bg-white/80 px-4 py-3">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isThinking}
              rows={2}
              placeholder="Nachricht eingeben… (Enter zum Senden)"
              className="flex-1 resize-none rounded-xl border border-[color:var(--color-line)] bg-white px-3 py-2 text-sm text-[color:var(--color-ink)] placeholder:text-[color:var(--color-mist)] focus:outline-none focus:ring-2 focus:ring-[color:var(--color-clay)] disabled:opacity-50"
            />
            <button
              type="button"
              onClick={sendMessage}
              disabled={!input.trim() || isThinking}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[color:var(--color-clay)] text-white transition-opacity disabled:opacity-40"
              aria-label="Senden"
            >
              <Send size={16} />
            </button>
          </div>
          <p className="mt-1.5 text-xs text-[color:var(--color-mist)]">
            Shift+Enter für Zeilenumbruch
          </p>
        </div>
      </div>

      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/10"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}
    </>
  );
}
