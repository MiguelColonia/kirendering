import axios from "axios";
import { API_BASE_URL } from "./http";
import type { DiffusionGalleryItem, DiffusionMode } from "../types/diffusion";

export type DiffusionJobStartResponse = {
  job_id: string;
  status: string;
  project_id: string;
};

export async function createDiffusion(
  projectId: string,
  file: File,
  params: {
    mode: DiffusionMode;
    prompt: string;
    negative_prompt?: string;
    guidance_scale?: number;
    image_guidance_scale?: number;
    controlnet_conditioning_scale?: number;
    seed?: number | null;
  },
): Promise<DiffusionJobStartResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", params.mode);
  formData.append("prompt", params.prompt);
  if (params.negative_prompt) formData.append("negative_prompt", params.negative_prompt);
  if (params.guidance_scale != null)
    formData.append("guidance_scale", String(params.guidance_scale));
  if (params.image_guidance_scale != null)
    formData.append("image_guidance_scale", String(params.image_guidance_scale));
  if (params.controlnet_conditioning_scale != null)
    formData.append(
      "controlnet_conditioning_scale",
      String(params.controlnet_conditioning_scale),
    );
  if (params.seed != null) formData.append("seed", String(params.seed));

  const response = await axios.post<DiffusionJobStartResponse>(
    `${API_BASE_URL}/api/projects/${projectId}/diffusion`,
    formData,
    { timeout: 660_000 },
  );
  return response.data;
}

export async function listDiffusion(projectId: string): Promise<DiffusionGalleryItem[]> {
  const response = await axios.get<DiffusionGalleryItem[]>(
    `${API_BASE_URL}/api/projects/${projectId}/diffusion`,
  );
  return response.data;
}
