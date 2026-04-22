import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { LandingPage } from "./LandingPage";
import { renderWithProviders } from "../test-utils";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

describe("LandingPage", () => {
  it("zeigt Hero-Aktionen und Kernkarten", () => {
    renderWithProviders(<LandingPage />);

    expect(screen.getByText("landing.hero.title")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "landing.hero.primary_action" }),
    ).toHaveAttribute("href", "/projekte/neu");
    expect(
      screen.getByRole("link", { name: "landing.hero.secondary_action" }),
    ).toHaveAttribute("href", "/projekte");
    expect(screen.getByText("landing.cards.create.title")).toBeInTheDocument();
    expect(screen.getByText("landing.cards.list.title")).toBeInTheDocument();
  });
});