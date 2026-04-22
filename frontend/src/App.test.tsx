import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "de" },
  }),
}));

vi.mock("./pages/LandingPage", () => ({
  LandingPage: () => <div>landing-page</div>,
}));

vi.mock("./pages/ProjectListPage", () => ({
  ProjectListPage: ({
    showCreateDialog = false,
  }: {
    showCreateDialog?: boolean;
  }) => <div>{showCreateDialog ? "projects-page-create" : "projects-page"}</div>,
}));

vi.mock("./pages/ProjectEditorPage", () => ({
  ProjectEditorPage: () => <div>project-editor-page</div>,
}));

vi.mock("./pages/ProjectRendersPage", () => ({
  ProjectRendersPage: () => <div>project-renders-page</div>,
}));

describe("App", () => {
  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("rendert die Shell und öffnet /projekte/neu mit Dialog-Route", async () => {
    window.history.pushState({}, "", "/projekte/neu");

    render(<App />);

    expect(screen.getByText("app.title")).toBeInTheDocument();
    expect(screen.getByText("nav.projects")).toBeInTheDocument();
    expect(await screen.findByText("projects-page-create")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("de");
  });

  it("leitet unbekannte Routen auf die Landingpage um", async () => {
    window.history.pushState({}, "", "/nicht-vorhanden");

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("landing-page")).toBeInTheDocument();
    });
  });
});