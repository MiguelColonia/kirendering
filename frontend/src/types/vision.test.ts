import { describe, expect, it } from "vitest";
import type {
  DetectedLabel,
  DetectedSymbol,
  PixelBBox,
  PlanInterpretation,
  RoomRegion,
} from "./vision";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function bbox(x = 0, y = 0, width = 10, height = 10): PixelBBox {
  return { x, y, width, height };
}

function minimalInterpretation(
  overrides: Partial<PlanInterpretation> = {},
): PlanInterpretation {
  return {
    image_width_px: 800,
    image_height_px: 600,
    meters_per_pixel: null,
    detected_symbols: [],
    detected_labels: [],
    room_regions: [],
    wall_segment_count: 0,
    has_draft_building: false,
    is_draft: true,
    review_required: true,
    warnings: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// PixelBBox
// ---------------------------------------------------------------------------

describe("PixelBBox", () => {
  it("akzeptiert ganzzahlige Pixelkoordinaten", () => {
    const b = bbox(10, 20, 30, 40);
    expect(b.x).toBe(10);
    expect(b.y).toBe(20);
    expect(b.width).toBe(30);
    expect(b.height).toBe(40);
  });
});

// ---------------------------------------------------------------------------
// DetectedSymbol
// ---------------------------------------------------------------------------

describe("DetectedSymbol", () => {
  it("hat symbol_type, bbox_px und confidence", () => {
    const sym: DetectedSymbol = {
      symbol_type: "DOOR",
      bbox_px: bbox(5, 5, 20, 10),
      confidence: 0.9,
    };
    expect(sym.symbol_type).toBe("DOOR");
    expect(sym.confidence).toBeGreaterThan(0);
    expect(sym.confidence).toBeLessThanOrEqual(1);
  });

  it("erlaubt alle bekannten Symboltypen", () => {
    const symbolTypes = ["DOOR", "WINDOW", "STAIR", "COLUMN", "UNKNOWN"];
    for (const st of symbolTypes) {
      const sym: DetectedSymbol = {
        symbol_type: st,
        bbox_px: bbox(),
        confidence: 0.5,
      };
      expect(sym.symbol_type).toBe(st);
    }
  });
});

// ---------------------------------------------------------------------------
// DetectedLabel
// ---------------------------------------------------------------------------

describe("DetectedLabel", () => {
  it("kann room_type als null haben wenn kein Raumtyp erkannt wurde", () => {
    const lbl: DetectedLabel = {
      bbox_px: bbox(10, 10, 80, 15),
      raw_text: "M 1:100",
      room_type: null,
    };
    expect(lbl.room_type).toBeNull();
    expect(lbl.raw_text).toBe("M 1:100");
  });

  it("enthält den erkannten Raumtyp als String", () => {
    const lbl: DetectedLabel = {
      bbox_px: bbox(20, 30, 60, 12),
      raw_text: "Wohnzimmer",
      room_type: "LIVING",
    };
    expect(lbl.room_type).toBe("LIVING");
  });
});

// ---------------------------------------------------------------------------
// RoomRegion
// ---------------------------------------------------------------------------

describe("RoomRegion", () => {
  it("hat room_type, center_px und approx_bbox_px", () => {
    const region: RoomRegion = {
      label_text: "Schlafzimmer",
      room_type: "BEDROOM",
      center_px: [100, 80],
      approx_bbox_px: bbox(50, 30, 100, 100),
    };
    expect(region.room_type).toBe("BEDROOM");
    expect(region.center_px).toHaveLength(2);
    expect(region.label_text).toBe("Schlafzimmer");
  });

  it("erlaubt label_text als null", () => {
    const region: RoomRegion = {
      label_text: null,
      room_type: "BATHROOM",
      center_px: [50, 60],
      approx_bbox_px: bbox(20, 40, 60, 40),
    };
    expect(region.label_text).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// PlanInterpretation
// ---------------------------------------------------------------------------

describe("PlanInterpretation", () => {
  it("ist immer ein Entwurf der manueller Prüfung bedarf", () => {
    const interp = minimalInterpretation();
    expect(interp.is_draft).toBe(true);
    expect(interp.review_required).toBe(true);
  });

  it("erlaubt meters_per_pixel als null wenn kein Maßstab erkannt wurde", () => {
    const interp = minimalInterpretation({ meters_per_pixel: null });
    expect(interp.meters_per_pixel).toBeNull();
  });

  it("enthält die Bilddimensionen in Pixeln", () => {
    const interp = minimalInterpretation({
      image_width_px: 1024,
      image_height_px: 768,
    });
    expect(interp.image_width_px).toBe(1024);
    expect(interp.image_height_px).toBe(768);
  });

  it("enthält eine leere Liste für erkannte Räume wenn keine gefunden wurden", () => {
    const interp = minimalInterpretation({ room_regions: [] });
    expect(interp.room_regions).toHaveLength(0);
  });

  it("enthält Warnungen als String-Array", () => {
    const warnings = [
      "Kein Maßstab erkannt.",
      "Keine Symbole identifiziert.",
    ];
    const interp = minimalInterpretation({ warnings });
    expect(interp.warnings).toHaveLength(2);
    expect(interp.warnings[0]).toContain("Maßstab");
  });

  it("wall_segment_count gibt die Anzahl der erkannten Wandsegmente an", () => {
    const interp = minimalInterpretation({ wall_segment_count: 42 });
    expect(interp.wall_segment_count).toBe(42);
  });

  it("has_draft_building ist false wenn kein BIM-Entwurf erstellt werden konnte", () => {
    const interp = minimalInterpretation({
      meters_per_pixel: null,
      has_draft_building: false,
    });
    expect(interp.has_draft_building).toBe(false);
  });

  it("hat vollständige Interpretation mit allen Listen", () => {
    const interp = minimalInterpretation({
      meters_per_pixel: 0.025,
      has_draft_building: true,
      detected_symbols: [
        {
          symbol_type: "WINDOW",
          bbox_px: bbox(100, 50, 20, 5),
          confidence: 0.7,
        },
      ],
      detected_labels: [
        {
          bbox_px: bbox(30, 60, 70, 12),
          raw_text: "Küche",
          room_type: "KITCHEN",
        },
      ],
      room_regions: [
        {
          label_text: "Küche",
          room_type: "KITCHEN",
          center_px: [65, 120],
          approx_bbox_px: bbox(30, 80, 70, 80),
        },
      ],
      wall_segment_count: 12,
      warnings: [],
    });

    expect(interp.detected_symbols).toHaveLength(1);
    expect(interp.detected_labels).toHaveLength(1);
    expect(interp.room_regions).toHaveLength(1);
    expect(interp.meters_per_pixel).toBeCloseTo(0.025);
    expect(interp.has_draft_building).toBe(true);
  });
});
