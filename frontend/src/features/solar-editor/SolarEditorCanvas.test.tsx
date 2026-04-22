import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SolarEditorCanvas } from "./SolarEditorCanvas";
import type { Point2D } from "../../types/project";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("react-konva", () => ({
  Stage: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Layer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => <div />,
  Text: () => <div />,
  Circle: () => <button type="button" />,
}));

describe("SolarEditorCanvas", () => {
  it("verwendet die ausgewählte Rasterweite für neue Punkte", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    const points: Point2D[] = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
      { x: 0, y: 10 },
    ];

    render(
      <SolarEditorCanvas
        points={points}
        northAngleDeg={0}
        onChange={handleChange}
        onNorthAngleChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "5 m" }));
    await user.click(
      screen.getByRole("button", { name: "solar_editor.point_add" }),
    );

    expect(handleChange).toHaveBeenLastCalledWith([
      ...points,
      { x: 5, y: 10 },
    ]);
  });
});