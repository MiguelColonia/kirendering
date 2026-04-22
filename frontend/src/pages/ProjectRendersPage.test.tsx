import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProjectRendersPage } from "./ProjectRendersPage";
import { renderWithProviders } from "../test-utils";
import type { DiffusionGalleryItem } from "../types/diffusion";
import type { ProjectDetail, RenderGalleryItem } from "../types/project";
import {
  createDefaultProgram,
  createDefaultSolar,
} from "../features/projects/projectDefaults";

type JobStreamHandlers = {
  onEvent: (event: {
    event: string;
    job_id: string;
    timestamp: string;
    data: Record<string, unknown>;
  }) => void;
  onOpen?: () => void;
  onReconnect?: (attempt: number) => void;
  onSocketError?: (error: { message: string }) => void;
  onClose?: (reason: string) => void;
};

const {
  mockUseProjectDetailQuery,
  mockListRenders,
  mockListDiffusion,
  mockCreateRender,
} = vi.hoisted(() => ({
  mockUseProjectDetailQuery: vi.fn(),
  mockListRenders: vi.fn(),
  mockListDiffusion: vi.fn(),
  mockCreateRender: vi.fn(),
}));

const streamState = vi.hoisted(() => ({
  jobId: null as string | null,
  handlers: null as JobStreamHandlers | null,
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      options?: string | { count?: number; name?: string },
    ) => {
      if (typeof options === "string") {
        return options;
      }
      if (typeof options?.count !== "undefined") {
        return key.replace("{{count}}", String(options.count));
      }
      if (typeof options?.name !== "undefined") {
        return key.replace("{{name}}", String(options.name));
      }
      return key;
    },
  }),
}));

vi.mock("../features/projects/useProjectsQuery", () => ({
  useProjectDetailQuery: mockUseProjectDetailQuery,
}));

vi.mock("../api/projects", () => ({
  createRender: mockCreateRender,
  listRenders: mockListRenders,
  resolveApiUrl: (path: string) => path,
}));

vi.mock("../api/diffusion", () => ({
  listDiffusion: mockListDiffusion,
}));

vi.mock("../hooks/useJobStream", () => ({
  useJobStream: (jobId: string | null, handlers: JobStreamHandlers) => {
    streamState.jobId = jobId;
    streamState.handlers = handlers;
  },
}));

vi.mock("../features/diffusion/DiffusionComposerDialog", () => ({
  DiffusionComposerDialog: ({
    projectId,
    initialImageUrl,
    onClose,
  }: {
    projectId: string;
    initialImageUrl?: string;
    onClose: () => void;
  }) => (
    <div>
      <span>diffusion-dialog:{projectId}:{initialImageUrl ?? "none"}</span>
      <button type="button" onClick={onClose}>
        close-diffusion-dialog
      </button>
    </div>
  ),
}));

function buildProject(hasIfcOutput = true): ProjectDetail {
  return {
    id: "project-1",
    name: "Projekt Render",
    description: "Beschreibung",
    status: "feasible",
    latest_version_number: 2,
    created_at: "2026-04-22T10:00:00.000Z",
    updated_at: "2026-04-22T10:00:00.000Z",
    current_version: {
      id: "version-1",
      version_number: 2,
      solar: createDefaultSolar(),
      program: createDefaultProgram(),
      solution: null,
      generated_outputs: hasIfcOutput
        ? [
            {
              id: "output-1",
              output_type: "IFC",
              file_path: "/tmp/model.ifc",
              media_type: "application/octet-stream",
              metadata: {},
              created_at: "2026-04-22T10:00:00.000Z",
            },
          ]
        : [],
      created_at: "2026-04-22T10:00:00.000Z",
      updated_at: "2026-04-22T10:00:00.000Z",
    },
  };
}

function buildRenderItem(): RenderGalleryItem {
  return {
    id: "render-1",
    project_id: "project-1",
    version_id: "version-1",
    version_number: 2,
    view: "exterior",
    prompt: "goldene Abendsonne",
    image_url: "/images/render-1.png",
    download_url: "/downloads/render-1.png",
    media_type: "image/png",
    created_at: "2026-04-22T10:00:00.000Z",
    has_reference_image: true,
    reference_image_name: "referenz.png",
    duration_seconds: 95,
    estimated_total_seconds: 120,
    device_used: "RX 6600",
  };
}

function buildDiffusionItem(): DiffusionGalleryItem {
  return {
    id: "diffusion-1",
    project_id: "project-1",
    version_id: "version-1",
    version_number: 2,
    mode: "img2img_controlnet_depth",
    prompt: "mehr Holz und warme Fassade",
    image_url: "/images/diffusion-1.png",
    download_url: "/downloads/diffusion-1.png",
    media_type: "image/png",
    created_at: "2026-04-22T10:05:00.000Z",
    duration_seconds: 80,
    device_used: "RX 6600",
    warnings: ["check contrast"],
  };
}

function renderPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={["/projekte/project-1/renders"]}>
      <Routes>
        <Route path="/projekte/:id/renders" element={<ProjectRendersPage />} />
      </Routes>
    </MemoryRouter>,
    { withRouter: false },
  );
}

afterEach(() => {
  vi.clearAllMocks();
  streamState.jobId = null;
  streamState.handlers = null;
});

describe("ProjectRendersPage", () => {
  it("zeigt leere Galerien und öffnet Composer-Flächen", async () => {
    const user = userEvent.setup();
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(),
      isLoading: false,
    });
    mockListRenders.mockResolvedValue([]);
    mockListDiffusion.mockResolvedValue([]);

    renderPage();

    await waitFor(() => {
      expect(mockListRenders).toHaveBeenCalled();
      expect(mockListDiffusion).toHaveBeenCalled();
    });

    expect(
      await screen.findByText("renders.gallery.empty"),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("diffusion.gallery_empty"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "renders.new_render" }));
    expect(screen.getByText("renders.form.fields.view")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("renders.form.prompt_placeholder"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "diffusion.trigger" }));
    expect(
      screen.getByText("diffusion-dialog:project-1:none"),
    ).toBeInTheDocument();
  });

  it("startet einen Render mit Ansicht, Prompt und Referenzbild", async () => {
    const user = userEvent.setup();
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(true),
      isLoading: false,
    });
    mockListRenders.mockResolvedValue([]);
    mockListDiffusion.mockResolvedValue([]);
    mockCreateRender.mockResolvedValue({
      job_id: "job-7",
      status: "queued",
      project_id: "project-1",
    });

    const { container, queryClient } = renderPage();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await waitFor(() => {
      expect(mockListRenders).toHaveBeenCalled();
      expect(mockListDiffusion).toHaveBeenCalled();
    });

    await user.click(screen.getByRole("button", { name: "renders.new_render" }));
    await user.selectOptions(screen.getByRole("combobox"), "interior");
    await user.type(
      screen.getByPlaceholderText("renders.form.prompt_placeholder"),
      "ruhiger Innenraum mit warmem Licht",
    );

    const fileInput = container.querySelector("input[type='file']");
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Datei-Input nicht gefunden");
    }

    await user.upload(
      fileInput,
      new File(["ref"], "referenz.png", { type: "image/png" }),
    );
    await user.click(screen.getByRole("button", { name: "renders.form.submit" }));

    await waitFor(() => {
      expect(mockCreateRender).toHaveBeenCalledWith(
        "project-1",
        expect.objectContaining({
          view: "interior",
          prompt: "ruhiger Innenraum mit warmem Licht",
          reference_image_name: "referenz.png",
          reference_image_media_type: "image/png",
          reference_image_base64: expect.any(String),
        }),
      );
    });
    await waitFor(() => {
      expect(streamState.jobId).toBe("job-7");
    });

    expect(screen.getByText("renders.connection.connecting")).toBeInTheDocument();
    expect(screen.getByText("renders.status.queued")).toBeInTheDocument();

    await act(async () => {
      streamState.handlers?.onOpen?.();
      streamState.handlers?.onEvent({
        event: "progress",
        job_id: "job-7",
        timestamp: "2026-04-22T10:01:00.000Z",
        data: { step: "lighting" },
      });
    });

    expect(screen.getByText("renders.connection.connected")).toBeInTheDocument();
    expect(screen.getByText("progress")).toBeInTheDocument();

    await act(async () => {
      streamState.handlers?.onEvent({
        event: "finished",
        job_id: "job-7",
        timestamp: "2026-04-22T10:03:00.000Z",
        data: {},
      });
    });

    await waitFor(() => {
      expect(screen.getByText("renders.status.finished")).toBeInTheDocument();
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["renders", "project-1"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["project", "project-1"] });
  });

  it("muestra aviso y bloquea el envío cuando no hay IFC", async () => {
    const user = userEvent.setup();
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(false),
      isLoading: false,
    });
    mockListRenders.mockResolvedValue([]);
    mockListDiffusion.mockResolvedValue([]);

    renderPage();

    await user.click(screen.getByRole("button", { name: "renders.new_render" }));

    expect(screen.getByText("renders.form.ifc_hint")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "renders.form.submit" }),
    ).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "common.cancel" }));

    expect(
      screen.queryByText("renders.form.fields.view"),
    ).not.toBeInTheDocument();
  });

  it("muestra tarjetas de galería y abre la refinación con la imagen origen", async () => {
    const user = userEvent.setup();
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(true),
      isLoading: false,
    });
    mockListRenders.mockResolvedValue([buildRenderItem()]);
    mockListDiffusion.mockResolvedValue([buildDiffusionItem()]);

    const { queryClient } = renderPage();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    expect(await screen.findByText("goldene Abendsonne")).toBeInTheDocument();
    expect(screen.getByText("mehr Holz und warme Fassade")).toBeInTheDocument();
    expect(screen.getByText("check contrast")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "renders.gallery.download" }),
    ).toHaveAttribute("href", "/downloads/render-1.png");
    expect(
      screen.getByRole("link", { name: "common.download" }),
    ).toHaveAttribute("href", "/downloads/diffusion-1.png");

    const refineButtons = screen.getAllByRole("button", {
      name: "diffusion.refine",
    });

    await user.click(refineButtons[0]);
    expect(
      screen.getByText("diffusion-dialog:project-1:/images/render-1.png"),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "close-diffusion-dialog" }),
    );
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["diffusion", "project-1"],
      });
    });

    await user.click(refineButtons[1]);
    expect(
      screen.getByText("diffusion-dialog:project-1:/images/diffusion-1.png"),
    ).toBeInTheDocument();
  });
});