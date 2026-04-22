import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProjectEditorPage } from "./ProjectEditorPage";
import { renderWithProviders } from "../test-utils";
import type { ProjectDetail } from "../types/project";
import {
  createDefaultProgram,
  createDefaultSolar,
} from "../features/projects/projectDefaults";

const { mockUseProjectDetailQuery, mockDeleteProject, mockNavigate } = vi.hoisted(() => ({
  mockUseProjectDetailQuery: vi.fn(),
  mockDeleteProject: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { count?: number; name?: string }) => {
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

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../api/projects", () => ({
  deleteProject: mockDeleteProject,
}));

vi.mock("../features/projects/useProjectsQuery", () => ({
  useProjectDetailQuery: mockUseProjectDetailQuery,
}));

vi.mock("../features/generation/ProjectGenerationPanel", () => ({
  ProjectGenerationPanel: ({ projectId }: { projectId: string }) => (
    <div>generation-panel:{projectId}</div>
  ),
}));

vi.mock("../features/plan-analyzer/PlanAnalyzerDialog", () => ({
  PlanAnalyzerDialog: ({
    projectId,
    onClose,
  }: {
    projectId: string;
    onClose: () => void;
  }) => (
    <div>
      <span>plan-analyzer-dialog:{projectId}</span>
      <button type="button" onClick={onClose}>
        close-plan-analyzer
      </button>
    </div>
  ),
}));

vi.mock("../features/program-editor/ProjectProgramEditor", () => ({
  ProjectProgramEditor: () => <div>program-editor</div>,
}));

vi.mock("../features/solar-editor/ProjectSolarEditor", () => ({
  ProjectSolarEditor: () => <div>solar-editor</div>,
}));

vi.mock("../features/chat/ChatPanel", () => ({
  ChatPanel: ({ projectId }: { projectId: string }) => <div>chat-panel:{projectId}</div>,
}));

vi.mock("../features/ifc-viewer/IfcModelWorkspace", () => ({
  IfcModelWorkspace: () => <div>ifc-model-workspace</div>,
}));

function buildProject(hasIfcOutput = false): ProjectDetail {
  return {
    id: "project-1",
    name: "Projekt Editor",
    description: "Beschreibung",
    status: "draft",
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

function renderPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={["/projekte/project-1"]}>
      <Routes>
        <Route path="/projekte/:id" element={<ProjectEditorPage />} />
      </Routes>
    </MemoryRouter>,
    { withRouter: false },
  );
}

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("ProjectEditorPage", () => {
  it("zeigt ohne IFC den Grundstücksbereich, Chat und Model-Hinweis", () => {
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(false),
      isLoading: false,
    });

    renderPage();

    expect(screen.getByText("solar-editor")).toBeInTheDocument();
    expect(screen.getByText("generation-panel:project-1")).toBeInTheDocument();
    expect(screen.getByText("chat-panel:project-1")).toBeInTheDocument();
    expect(screen.getByText("ifc_viewer.model_tab_hint")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "project_editor.tabs.model" }),
    ).not.toBeInTheDocument();
  });

  it("abre el analizador y mantiene los enlaces de navegación esperados", async () => {
    const user = userEvent.setup();
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(false),
      isLoading: false,
    });

    renderPage();

    await user.click(screen.getByRole("button", { name: "plan_analyzer.trigger" }));

    expect(screen.getByText("plan-analyzer-dialog:project-1")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "project_editor.render_gallery" }),
    ).toHaveAttribute("href", "/projekte/project-1/renders");
    expect(
      screen.getByRole("link", { name: "project_editor.back_to_list" }),
    ).toHaveAttribute("href", "/projekte");

    await user.click(screen.getByRole("button", { name: "close-plan-analyzer" }));

    expect(
      screen.queryByText("plan-analyzer-dialog:project-1"),
    ).not.toBeInTheDocument();
  });

  it("borra el proyecto tras confirmar y vuelve a la lista", async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    mockDeleteProject.mockResolvedValue(undefined);
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(true),
      isLoading: false,
    });

    const { queryClient } = renderPage();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const removeSpy = vi.spyOn(queryClient, "removeQueries");

    await user.click(
      screen.getByRole("button", { name: "project_editor.delete_project" }),
    );

    await waitFor(() => {
      expect(mockDeleteProject).toHaveBeenCalledWith("project-1");
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/projekte");
    });

    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["projects"] });
    expect(removeSpy).toHaveBeenCalledWith({
      queryKey: ["project", "project-1"],
    });
  });

  it("muestra el error de borrado si la operación falla", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockDeleteProject.mockRejectedValue(new Error("delete failed"));
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(true),
      isLoading: false,
    });

    renderPage();

    await user.click(
      screen.getByRole("button", { name: "project_editor.delete_project" }),
    );

    expect(await screen.findByText("delete failed")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("lässt bei IFC-Ausgabe zwischen Programm und Modell wechseln", async () => {
    const user = userEvent.setup();
    mockUseProjectDetailQuery.mockReturnValue({
      data: buildProject(true),
      isLoading: false,
    });

    renderPage();

    await user.click(
      screen.getByRole("button", { name: "project_editor.tabs.program" }),
    );
    expect(screen.getByText("program-editor")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "project_editor.tabs.model" }),
    );
    expect(await screen.findByText("ifc-model-workspace")).toBeInTheDocument();
  });
});