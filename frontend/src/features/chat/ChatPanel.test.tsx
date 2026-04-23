import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "./ChatPanel";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  readonly url: string;
  onopen: ((event?: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event?: Event) => void) | null = null;
  close = vi.fn();
  send = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  emitOpen() {
    this.onopen?.();
  }

  emitMessage(payload: Record<string, unknown>) {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(payload) }),
    );
  }
}

describe("ChatPanel", () => {
  const originalWebSocket = globalThis.WebSocket;

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("WebSocket", originalWebSocket);
  });

  it("setzt Nachrichten zurück, wenn das Projekt wechselt", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ChatPanel projectId="projekt-a" />);

    await user.click(
      screen.getByRole("button", { name: "KI-Assistent öffnen" }),
    );
    await user.type(
      screen.getByPlaceholderText("Nachricht eingeben… (Enter zum Senden)"),
      "Hallo Projekt A",
    );
    await user.click(screen.getByRole("button", { name: "Senden" }));

    expect(screen.getByText("Hallo Projekt A")).toBeInTheDocument();

    rerender(<ChatPanel projectId="projekt-b" />);

    expect(screen.queryByText("Hallo Projekt A")).not.toBeInTheDocument();
  });

  it("sendet pro Projektsitzung eine stabile thread_id", async () => {
    const user = userEvent.setup();

    render(<ChatPanel projectId="projekt-a" />);

    await user.click(
      screen.getByRole("button", { name: "KI-Assistent öffnen" }),
    );
    await user.type(
      screen.getByPlaceholderText("Nachricht eingeben… (Enter zum Senden)"),
      "Erste Nachricht",
    );
    await user.click(screen.getByRole("button", { name: "Senden" }));

    expect(MockWebSocket.instances).toHaveLength(1);
    await act(async () => {
      MockWebSocket.instances[0].emitOpen();
      MockWebSocket.instances[0].emitMessage({
        type: "done",
        response: "Antwort 1",
        feasible: true,
        solution: null,
      });
    });

    const firstPayload = JSON.parse(
      MockWebSocket.instances[0].send.mock.calls[0][0],
    ) as {
      message: string;
      thread_id: string;
    };

    expect(firstPayload).toMatchObject({ message: "Erste Nachricht" });
    expect(firstPayload.thread_id).toMatch(/^projekt-a-/);

    await user.type(
      screen.getByPlaceholderText("Nachricht eingeben… (Enter zum Senden)"),
      "Zweite Nachricht",
    );
    await user.click(screen.getByRole("button", { name: "Senden" }));

    expect(MockWebSocket.instances).toHaveLength(2);
    await act(async () => {
      MockWebSocket.instances[1].emitOpen();
    });

    const secondPayload = JSON.parse(
      MockWebSocket.instances[1].send.mock.calls[0][0],
    ) as {
      message: string;
      thread_id: string;
    };

    expect(secondPayload).toMatchObject({ message: "Zweite Nachricht" });
    expect(secondPayload.thread_id).toBe(firstPayload.thread_id);
  });
});
