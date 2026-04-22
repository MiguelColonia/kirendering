export type DiffusionMode =
  | "img2img_controlnet_depth"
  | "img2img_controlnet_canny"
  | "instruct_pix2pix";

export type DiffusionGalleryItem = {
  id: string;
  project_id: string;
  version_id: string;
  version_number: number;
  mode: DiffusionMode;
  prompt: string | null;
  image_url: string;
  download_url: string;
  media_type: string | null;
  created_at: string;
  duration_seconds: number | null;
  device_used: string | null;
  warnings: string[];
};
