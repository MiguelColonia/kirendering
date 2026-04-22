import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectSolarEditor } from "./ProjectSolarEditor";
import { renderWithProviders } from "../../test-utils";
import type { Point2D, ProjectDetail } from "../../types/project";
import { createDefaultProgram, createDefaultSolar } from "../projects/projectDefaults";

const VALID_POINTS: Point2D[] = [
  { x: 0, y: 0 },
  { x: 20, y: 0 },
  { x: 22, y: 16 },
  { x: 0, y: 16 },
];

const INVALID_POINTS: Point2D[] = [
  { x: 0, y: 0 },
  { x: 2, y: 0 },
];

const { mockPatchProjectSolar } = vi.hoisted(() => ({
  mockPatchProjectSolar: vi.fn(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("../../api/projects", () => ({
  patchProjectSolar: mockPatchProjectSolar,
}));

vi.mock("./SolarEditorCanvas", () => ({
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
      <p data-testid="solar-point-count">{points.length}</p>
      <button type="button" onClick={() => onChange(VALID_POINTS)}>
        mock-solar-valid
      </button>
      <button type="button" onClick={() => onChange(INVALID_POINTS)}>
        mock-solar-invalid
      </button>
      <button type="button" onClick={() => onNorthAngleChange(45)}>
        mock-solar-rotate
      </button>
    </div>
  ),
}));

function buildProject(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  const solar = createDefaultSolar();

  return {
    id: "project-1",
    name: "Projekt Solar",
    description: "Solar test",
    status: "draft",
    latest_version_number: 1,
    created_at: "2026-04-22T10:00:00.000Z",
    updated_at: "2026-04-22T10:00:00.000Z",
    current_version: {
      id: "version-1",
      version_number: 1,
      solar,
      program: createDefaultProgram(),
      solution: null,
      generated_outputs: [],
      created_at: "2026-04-22T10:00:00.000Z",
      updated_at: "2026-04-22T10:00:00.000Z",
    },
    ...overrides,
  };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProjectSolarEditor", () => {
  it("speichert das Grundstück über den Partial-Patch", async () => {
    const user = userEvent.setup();
    const updatedProject = buildProject({
      current_version: {
        ...buildProject().current_version!,
        solar: {
          ...createDefaultSolar(),
          contour: { points: VALID_POINTS },
          north_angle_deg: 45,
          max_buildable_height_m: 28,
        },
      },
    });
    mockPatchProjectSolar.mockResolvedValue(updatedProject);

    renderWithProviders(<ProjectSolarEditor project={buildProject()} />, {
      withRouter: false,
    });

    await user.clear(screen.getByLabelText("solar_editor.max_height"));
    await user.type(screen.getByLabelText("solar_editor.max_height"), "28");
    await user.click(screen.getByRole("button", { name: "mock-solar-valid" }));
    await user.click(screen.getByRole("button", { name: "mock-solar-rotate" }));
    await user.click(screen.getByRole("button", { name: "common.save" }));

    await waitFor(() => expect(mockPatchProjectSolar).toHaveBeenCalledTimes(1));

    expect(mockPatchProjectSolar).toHaveBeenCalledWith(
      "project-1",
      expect.objectContaining({
        max_buildable_height_m: 28,
        north_angle_deg: 45,
        contour: { points: VALID_POINTS },
      }),
    );

    await waitFor(() => {
      expect(screen.getByText("solar_editor.save_success")).toBeInTheDocument();
    });
  });

  it("deaktiviert Speichern bei ungültigem Polygon", async () => {
    const user = userEvent.setup();

    renderWithProviders(<ProjectSolarEditor project={buildProject()} />, {
      withRouter: false,
    });

    await user.click(screen.getByRole("button", { name: "mock-solar-invalid" }));

    expect(screen.getByRole("button", { name: "common.save" })).toBeDisabled();
  });

  it("deaktiviert Speichern bei maximaler Gebäudehöhe 0", async () => {
    const user = userEvent.setup();

    renderWithProviders(<ProjectSolarEditor project={buildProject()} />, {
      withRouter: false,
    });

    await user.clear(screen.getByLabelText("solar_editor.max_height"));

    expect(
      screen.getByText("program_editor.validation.positive_number"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "common.save" })).toBeDisabled();
  });
});