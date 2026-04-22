import { describe, expect, it } from "vitest";
import { clamp, formatArea, formatDate, polygonArea } from "./format";

describe("format utilities", () => {
  it("formatiert Flaechen im deutschen Format", () => {
    expect(formatArea(1234.56)).toBe("1.234,6 m²");
  });

  it("formatiert ISO-Datumswerte fuer die UI", () => {
    expect(formatDate("2026-04-22T10:00:00.000Z")).toMatch(/2026/);
  });

  it("berechnet Polygonflaechen und behandelt unvollstaendige Polygone", () => {
    expect(
      polygonArea([
        { x: 0, y: 0 },
        { x: 4, y: 0 },
      ]),
    ).toBe(0);

    expect(
      polygonArea([
        { x: 0, y: 0 },
        { x: 4, y: 0 },
        { x: 4, y: 3 },
        { x: 0, y: 3 },
      ]),
    ).toBe(12);
  });

  it("begrenzt Werte innerhalb des erlaubten Bereichs", () => {
    expect(clamp(-5, 0, 10)).toBe(0);
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(50, 0, 10)).toBe(10);
  });
});