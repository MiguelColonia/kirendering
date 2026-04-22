import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { DiffusionComposerDialog } from "./DiffusionComposerDialog";
import { renderWithProviders } from "../../test-utils";
import type {
  JobStreamCloseReason,
  JobStreamError,
} from "../../hooks/useJobStream";
import type { JobEvent } from "../../types/project";

type JobStreamHandlers = {
  onEvent: (event: JobEvent) => void;
  onOpen?: () => void;
  onReconnect?: (attempt: number) => void;
  onSocketError?: (error: JobStreamError) => void;
  onClose?: (reason: JobStreamCloseReason) => void;
};

const streamState = vi.hoisted(() => ({
  createDiffusion: vi.fn(),
  jobId: null as string | null,
  handlers: null as JobStreamHandlers | null,
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("../../api/diffusion", () => ({
  createDiffusion: streamState.createDiffusion,
}));

vi.mock("../../hooks/useJobStream", () => ({
  useJobStream: (jobId: string | null, handlers: JobStreamHandlers) => {
    streamState.jobId = jobId;
    streamState.handlers = handlers;
  },
}));

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", {
    writable: true,
    value: vi.fn(() => "blob:preview"),
  });
});

afterEach(() => {
  vi.clearAllMocks();
  streamState.jobId = null;
  streamState.handlers = null;
});

describe("DiffusionComposerDialog", () => {
  it("bleibt im Processing-Zustand bis das Finished-Event eintrifft", async () => {
    const user = userEvent.setup();
    streamState.createDiffusion.mockResolvedValue({
      job_id: "job-1",
      status: "queued",
      project_id: "project-1",
    });

    const { container, queryClient } = renderWithProviders(
      <DiffusionComposerDialog projectId="project-1" onClose={vi.fn()} />,
      { withRouter: false },
    );
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const fileInput = container.querySelector("input[type='file']");
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Datei-Input nicht gefunden");
    }

    await user.upload(
      fileInput,
      new File(["image"], "fassade.png", { type: "image/png" }),
    );
    await user.type(
      screen.getByPlaceholderText("diffusion.compose.prompt_placeholder"),
      "warme Holzfassade mit Balkon",
    );
    await user.click(screen.getByRole("button", { name: "diffusion.compose.submit" }));

    await waitFor(() => {
      expect(streamState.createDiffusion).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(streamState.jobId).toBe("job-1");
    });

    expect(screen.getByText("diffusion.processing.title")).toBeInTheDocument();
    expect(screen.queryByText("diffusion.done.title")).not.toBeInTheDocument();

    await act(async () => {
      streamState.handlers?.onOpen?.();
      streamState.handlers?.onEvent({
        event: "progress",
        job_id: "job-1",
        timestamp: "2026-04-22T10:00:00.000Z",
        data: {},
      });
    });

    expect(
      screen.getByText("generation.connection.connected"),
    ).toBeInTheDocument();
    expect(screen.queryByText("diffusion.done.title")).not.toBeInTheDocument();

    await act(async () => {
      streamState.handlers?.onEvent({
        event: "finished",
        job_id: "job-1",
        timestamp: "2026-04-22T10:01:00.000Z",
        data: {},
      });
    });

    await waitFor(() => {
      expect(screen.getByText("diffusion.done.title")).toBeInTheDocument();
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["diffusion", "project-1"],
    });
  });

  it("zeigt Fehlerzustand bei fehlgeschlagenem Job und erlaubt Retry", async () => {
    const user = userEvent.setup();
    streamState.createDiffusion.mockResolvedValue({
      job_id: "job-2",
      status: "queued",
      project_id: "project-1",
    });

    const { container } = renderWithProviders(
      <DiffusionComposerDialog projectId="project-1" onClose={vi.fn()} />,
      { withRouter: false },
    );

    const fileInput = container.querySelector("input[type='file']");
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Datei-Input nicht gefunden");
    }

    await user.upload(
      fileInput,
      new File(["image"], "fassade.png", { type: "image/png" }),
    );
    await user.type(
      screen.getByPlaceholderText("diffusion.compose.prompt_placeholder"),
      "ruhige Abendstimmung",
    );
    await user.click(screen.getByRole("button", { name: "diffusion.compose.submit" }));

    await waitFor(() => {
      expect(streamState.jobId).toBe("job-2");
    });

    await act(async () => {
      streamState.handlers?.onEvent({
        event: "failed",
        job_id: "job-2",
        timestamp: "2026-04-22T10:01:00.000Z",
        data: {},
      });
    });

    await waitFor(() => {
      expect(screen.getByText("diffusion.error.title")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "diffusion.error.retry" }));

    expect(screen.getByText("diffusion.compose.submit")).toBeInTheDocument();
  });

  it("zeigt Stream-Probleme waehrend der Verarbeitung an", async () => {
    const user = userEvent.setup();
    streamState.createDiffusion.mockResolvedValue({
      job_id: "job-3",
      status: "queued",
      project_id: "project-1",
    });

    const { container } = renderWithProviders(
      <DiffusionComposerDialog projectId="project-1" onClose={vi.fn()} />,
      { withRouter: false },
    );

    const fileInput = container.querySelector("input[type='file']");
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Datei-Input nicht gefunden");
    }

    await user.upload(
      fileInput,
      new File(["image"], "fassade.png", { type: "image/png" }),
    );
    await user.type(
      screen.getByPlaceholderText("diffusion.compose.prompt_placeholder"),
      "Materialitaet pruefen",
    );
    await user.click(screen.getByRole("button", { name: "diffusion.compose.submit" }));

    await waitFor(() => {
      expect(streamState.jobId).toBe("job-3");
    });

    await act(async () => {
      streamState.handlers?.onReconnect?.(1);
    });

    expect(
      screen.getByText("generation.connection.reconnecting"),
    ).toBeInTheDocument();
    expect(screen.getByText("generation.connection_lost")).toBeInTheDocument();

    await act(async () => {
      streamState.handlers?.onSocketError?.({ message: "socket down" });
    });

    expect(screen.getByText("generation.connection.error")).toBeInTheDocument();
    expect(screen.getByText("socket down")).toBeInTheDocument();

    await act(async () => {
      streamState.handlers?.onClose?.("completed");
    });

    expect(screen.getByText("generation.connection.closed")).toBeInTheDocument();
  });

  it("wechselt in den Fehlerzustand wenn der Start fehlschlaegt", async () => {
    const user = userEvent.setup();
    streamState.createDiffusion.mockRejectedValue(new Error("start failed"));

    const { container } = renderWithProviders(
      <DiffusionComposerDialog projectId="project-1" onClose={vi.fn()} />,
      { withRouter: false },
    );

    const fileInput = container.querySelector("input[type='file']");
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Datei-Input nicht gefunden");
    }

    await user.upload(
      fileInput,
      new File(["image"], "fassade.png", { type: "image/png" }),
    );
    await user.type(
      screen.getByPlaceholderText("diffusion.compose.prompt_placeholder"),
      "Abendstimmung mit Holzlamellen",
    );
    await user.click(screen.getByRole("button", { name: "diffusion.compose.submit" }));

    await waitFor(() => {
      expect(screen.getByText("diffusion.error.title")).toBeInTheDocument();
    });
    expect(screen.getByText("diffusion.error.generic")).toBeInTheDocument();
  });
});