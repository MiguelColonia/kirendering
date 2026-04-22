export type PixelBBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type DetectedSymbol = {
  symbol_type: string;
  bbox_px: PixelBBox;
  confidence: number;
};

export type DetectedLabel = {
  bbox_px: PixelBBox;
  raw_text: string;
  room_type: string | null;
};

export type RoomRegion = {
  label_text: string | null;
  room_type: string;
  center_px: [number, number];
  approx_bbox_px: PixelBBox;
};

export type PlanInterpretation = {
  image_width_px: number;
  image_height_px: number;
  meters_per_pixel: number | null;
  detected_symbols: DetectedSymbol[];
  detected_labels: DetectedLabel[];
  room_regions: RoomRegion[];
  wall_segment_count: number;
  has_draft_building: boolean;
  is_draft: boolean;
  review_required: boolean;
  warnings: string[];
};
