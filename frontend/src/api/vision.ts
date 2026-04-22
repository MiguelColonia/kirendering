import axios from "axios";
import { API_BASE_URL } from "./http";
import type { PlanInterpretation } from "../types/vision";

export async function analyzePlan(
  projectId: string,
  file: File,
): Promise<PlanInterpretation> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await axios.post<PlanInterpretation>(
    `${API_BASE_URL}/api/projects/${projectId}/vision/analyze`,
    formData,
    { timeout: 300_000 },
  );
  return response.data;
}
