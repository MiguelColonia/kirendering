import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProjectsListPanel } from "./ProjectsListPanel";
import { renderWithProviders } from "../../test-utils";

const { mockUseProjectsQuery } = vi.hoisted(() => ({
  mockUseProjectsQuery: vi.fn(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("./useProjectsQuery", () => ({
  useProjectsQuery: mockUseProjectsQuery,
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProjectsListPanel", () => {
  it("zeigt einen Loading-State", () => {
    mockUseProjectsQuery.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });

    renderWithProviders(<ProjectsListPanel />);

    expect(screen.getByText("common.loading")).toBeInTheDocument();
  });

  it("filtert Projekte nach Suchbegriff", async () => {
    const user = userEvent.setup();
    mockUseProjectsQuery.mockReturnValue({
      data: [
        {
          id: "project-a",
          name: "Alpha Hof",
          description: "Erstes Projekt",
          latest_version_number: 1,
          status: "draft",
          created_at: "2026-04-22T10:00:00.000Z",
          updated_at: "2026-04-22T10:00:00.000Z",
        },
        {
          id: "project-b",
          name: "Beta Haus",
          description: "Zweites Projekt",
          latest_version_number: 2,
          status: "feasible",
          created_at: "2026-04-22T10:00:00.000Z",
          updated_at: "2026-04-22T10:00:00.000Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderWithProviders(<ProjectsListPanel />);

    expect(screen.getByText("Alpha Hof")).toBeInTheDocument();
    expect(screen.getByText("Beta Haus")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("projects.list.search_placeholder"),
      "beta",
    );

    await waitFor(() => {
      expect(screen.queryByText("Alpha Hof")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Beta Haus")).toBeInTheDocument();
  });
});