import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectCreateDialog } from "./ProjectCreateDialog";
import { renderWithProviders } from "../../test-utils";
import type { Point2D, ProjectDetail } from "../../types/project";

const VALID_POINTS: Point2D[] = [
  { x: 0, y: 0 },
  { x: 18, y: 0 },
  { x: 18, y: 18 },
  { x: 0, y: 18 },
];

const INVALID_POINTS: Point2D[] = [
  { x: 0, y: 0 },
  { x: 4, y: 0 },
];

const { mockCreateProject, mockNavigate } = vi.hoisted(() => ({
  mockCreateProject: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
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

vi.mock("../../api/projects", () => ({
  createProject: mockCreateProject,
}));

vi.mock("../solar-editor/SolarEditorCanvas", () => ({
  SolarEditorCanvas: ({
    points,
    onChange,
    onNorthAngleChange,
  }: {
    points: Point2D[];
    onChange: (points: Point2D[]) => void;
    onNorthAngleChange: (deg: number) => void;
  }) => (
    <div>
      <p data-testid="site-point-count">{points.length}</p>
      <button type="button" onClick={() => onChange(VALID_POINTS)}>
        mock-site-valid
      </button>
      <button type="button" onClick={() => onChange(INVALID_POINTS)}>
        mock-site-invalid
      </button>
      <button type="button" onClick={() => onNorthAngleChange(45)}>
        mock-site-rotate
      </button>
    </div>
  ),
}));

function buildProject(id = "project-1"): ProjectDetail {
  return {
    id,
    name: "Projekt Alpha",
    description: "Beschreibung",
    status: "draft",
    latest_version_number: 1,
    created_at: "2026-04-22T10:00:00.000Z",
    updated_at: "2026-04-22T10:00:00.000Z",
    current_version: null,
  };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProjectCreateDialog", () => {
  it("erstellt ein Projekt mit bearbeitetem Grundstück und Programm", async () => {
    const user = userEvent.setup();
    mockCreateProject.mockResolvedValue(buildProject());

    renderWithProviders(
      <ProjectCreateDialog isOpen={true} onClose={vi.fn()} />,
    );

    await user.type(
      screen.getByLabelText("project_create.fields.name"),
      "Wohnhof Nord",
    );
    await user.type(
      screen.getByLabelText("project_create.fields.description"),
      "Innenhof mit Durchwegung",
    );

    await user.clear(screen.getByLabelText("solar_editor.max_height"));
    await user.type(screen.getByLabelText("solar_editor.max_height"), "25.5");
    await user.click(screen.getByRole("button", { name: "mock-site-rotate" }));

    await user.click(
      screen.getByRole("button", { name: "project_editor.tabs.program" }),
    );
    await user.clear(screen.getByLabelText("program_editor.floors"));
    await user.type(screen.getByLabelText("program_editor.floors"), "6");
    await user.clear(screen.getByLabelText("program_editor.unit_count"));
    await user.type(screen.getByLabelText("program_editor.unit_count"), "18");

    await user.click(
      screen.getByRole("button", { name: "project_create.submit" }),
    );

    await waitFor(() => expect(mockCreateProject).toHaveBeenCalledTimes(1));

    expect(mockCreateProject).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Wohnhof Nord",
        description: "Innenhof mit Durchwegung",
        solar: expect.objectContaining({
          max_buildable_height_m: 25.5,
          north_angle_deg: 45,
        }),
        program: expect.objectContaining({
          num_floors: 6,
          mix: [expect.objectContaining({ count: 18 })],
        }),
      }),
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/projekte/project-1");
    });
  });

  it("sperrt den Submit bei ungültigem Grundstück", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <ProjectCreateDialog isOpen={true} onClose={vi.fn()} />,
    );

    await user.type(
      screen.getByLabelText("project_create.fields.name"),
      "Ungültiges Projekt",
    );
    await user.click(screen.getByRole("button", { name: "mock-site-invalid" }));

    expect(screen.getByText("solar_editor.save_invalid")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "project_create.submit" }),
    ).toBeDisabled();
  });

  it("sperrt den Submit bei maximaler Gebäudehöhe 0", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <ProjectCreateDialog isOpen={true} onClose={vi.fn()} />,
    );

    await user.type(
      screen.getByLabelText("project_create.fields.name"),
      "Höhenfehler",
    );
    await user.clear(screen.getByLabelText("solar_editor.max_height"));

    expect(
      screen.getByText("program_editor.validation.positive_number"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "project_create.submit" }),
    ).toBeDisabled();
  });

  it("sperrt den Submit bei ungültigem Programm", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <ProjectCreateDialog isOpen={true} onClose={vi.fn()} />,
    );

    await user.type(
      screen.getByLabelText("project_create.fields.name"),
      "Programmfehler",
    );
    await user.click(
      screen.getByRole("button", { name: "project_editor.tabs.program" }),
    );
    await user.clear(screen.getByLabelText("program_editor.floors"));

    expect(
      screen.getByText("program_editor.validation.floors_minimum"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "project_create.submit" }),
    ).toBeDisabled();
  });
});