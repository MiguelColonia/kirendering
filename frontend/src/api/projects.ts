import { apiClient, API_BASE_URL, API_WS_BASE_URL } from "./http";
import type {
  CreateRenderPayload,
  JobStartResponse,
  JobStatus,
  Program,
  ProjectDetail,
  ProjectPayload,
  ProjectSummary,
  RenderGalleryItem,
  Solar,
} from "../types/project";

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await apiClient.get<ProjectSummary[]>("/api/projects");
  return response.data;
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  const response = await apiClient.get<ProjectDetail>(
    `/api/projects/${projectId}`,
  );
  return response.data;
}

export async function createProject(
  payload: ProjectPayload,
): Promise<ProjectDetail> {
  const response = await apiClient.post<ProjectDetail>(
    "/api/projects",
    payload,
  );
  return response.data;
}

export async function updateProject(
  projectId: string,
  payload: ProjectPayload,
): Promise<ProjectDetail> {
  const response = await apiClient.put<ProjectDetail>(
    `/api/projects/${projectId}`,
    payload,
  );
  return response.data;
}

export async function patchProjectProgram(
  projectId: string,
  program: Program,
): Promise<ProjectDetail> {
  const response = await apiClient.patch<ProjectDetail>(
    `/api/projects/${projectId}/program`,
    { program },
  );
  return response.data;
}

export async function patchProjectSolar(
  projectId: string,
  solar: Solar,
): Promise<ProjectDetail> {
  const response = await apiClient.patch<ProjectDetail>(
    `/api/projects/${projectId}/solar`,
    { solar },
  );
  return response.data;
}

export async function deleteProject(projectId: string): Promise<void> {
  await apiClient.delete(`/api/projects/${projectId}`);
}

export async function generateProject(
  projectId: string,
): Promise<JobStartResponse> {
  const response = await apiClient.post<JobStartResponse>(
    `/api/projects/${projectId}/generate`,
  );
  return response.data;
}

export async function createRender(
  projectId: string,
  payload: CreateRenderPayload,
): Promise<JobStartResponse> {
  const response = await apiClient.post<JobStartResponse>(
    `/api/projects/${projectId}/renders`,
    payload,
  );
  return response.data;
}

export async function listRenders(
  projectId: string,
): Promise<RenderGalleryItem[]> {
  const response = await apiClient.get<RenderGalleryItem[]>(
    `/api/projects/${projectId}/renders`,
  );
  return response.data;
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const response = await apiClient.get<JobStatus>(`/api/jobs/${jobId}`);
  return response.data;
}

export function buildOutputUrl(
  projectId: string,
  outputFormat: "ifc" | "dxf" | "xlsx" | "svg",
): string {
  return `${API_BASE_URL}/api/projects/${projectId}/outputs/${outputFormat}`;
}

export function buildJobStreamUrl(jobId: string): string {
  return `${API_WS_BASE_URL}/api/jobs/${jobId}/stream`;
}

export function buildChatStreamUrl(projectId: string): string {
  return `${API_WS_BASE_URL}/api/projects/${projectId}/chat/stream`;
}

export function resolveApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }

  return `${API_BASE_URL}${path}`;
}
