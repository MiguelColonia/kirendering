import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MockInstance } from "vitest";
import axios from "axios";
import { analyzePlan } from "./vision";
import type { PlanInterpretation } from "../types/vision";

vi.mock("axios");
vi.mock("./http", () => ({ API_BASE_URL: "http://localhost:8000" }));

const mockedAxiosPost = vi.mocked(axios.post) as MockInstance;

const MINIMAL_INTERPRETATION: PlanInterpretation = {
  image_width_px: 100,
  image_height_px: 80,
  meters_per_pixel: 0.02,
  detected_symbols: [],
  detected_labels: [],
  room_regions: [],
  wall_segment_count: 5,
  has_draft_building: false,
  is_draft: true,
  review_required: true,
  warnings: [],
};

describe("analyzePlan", () => {
  beforeEach(() => {
    mockedAxiosPost.mockResolvedValue({ data: MINIMAL_INTERPRETATION });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("ruft den richtigen Endpunkt auf", async () => {
    const file = new File([new Uint8Array(4)], "grundriss.png", {
      type: "image/png",
    });

    await analyzePlan("projekt-123", file);

    expect(mockedAxiosPost).toHaveBeenCalledOnce();
    const [url] = mockedAxiosPost.mock.calls[0] as [string, ...unknown[]];
    expect(url).toContain("/api/projects/projekt-123/vision/analyze");
  });

  it("sendet die Datei als FormData", async () => {
    const file = new File([new Uint8Array(8)], "plan.png", {
      type: "image/png",
    });

    await analyzePlan("projekt-abc", file);

    const [, formData] = mockedAxiosPost.mock.calls[0] as [
      string,
      FormData,
      ...unknown[],
    ];
    expect(formData).toBeInstanceOf(FormData);
    const uploadedFile = formData.get("file");
    expect(uploadedFile).toBeInstanceOf(File);
    expect((uploadedFile as File).name).toBe("plan.png");
  });

  it("setzt den Timeout auf 5 Minuten (300.000 ms)", async () => {
    const file = new File([new Uint8Array(4)], "plan.png", {
      type: "image/png",
    });

    await analyzePlan("projekt-x", file);

    const [, , config] = mockedAxiosPost.mock.calls[0] as [
      string,
      FormData,
      { timeout: number },
    ];
    expect(config.timeout).toBe(300_000);
  });

  it("gibt die PlanInterpretation des Backends zurück", async () => {
    const file = new File([new Uint8Array(4)], "plan.png", {
      type: "image/png",
    });

    const result = await analyzePlan("projekt-x", file);

    expect(result).toEqual(MINIMAL_INTERPRETATION);
    expect(result.is_draft).toBe(true);
    expect(result.review_required).toBe(true);
  });

  it("leitet Fehler von axios an den Aufrufer weiter", async () => {
    mockedAxiosPost.mockRejectedValue(new Error("Netzwerkfehler"));
    const file = new File([new Uint8Array(4)], "plan.png", {
      type: "image/png",
    });

    await expect(analyzePlan("projekt-x", file)).rejects.toThrow(
      "Netzwerkfehler",
    );
  });

  it("enthält die Projekt-ID korrekt in der URL", async () => {
    const projektId = "mein-projekt-2026";
    const file = new File([new Uint8Array(4)], "plan.png", {
      type: "image/png",
    });

    await analyzePlan(projektId, file);

    const [url] = mockedAxiosPost.mock.calls[0] as [string, ...unknown[]];
    expect(url).toContain(projektId);
  });
});
