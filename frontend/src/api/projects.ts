import { apiClient, API_BASE_URL, API_WS_BASE_URL } from './http'
import type {
  ChatMessage,
  JobStartResponse,
  JobStatus,
  ProjectDetail,
  ProjectPayload,
  ProjectSummary,
} from '../types/project'

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await apiClient.get<ProjectSummary[]>('/api/projects')
  return response.data
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  const response = await apiClient.get<ProjectDetail>(`/api/projects/${projectId}`)
  return response.data
}

export async function createProject(payload: ProjectPayload): Promise<ProjectDetail> {
  const response = await apiClient.post<ProjectDetail>('/api/projects', payload)
  return response.data
}

export async function updateProject(projectId: string, payload: ProjectPayload): Promise<ProjectDetail> {
  const response = await apiClient.put<ProjectDetail>(`/api/projects/${projectId}`, payload)
  return response.data
}

export async function deleteProject(projectId: string): Promise<void> {
  await apiClient.delete(`/api/projects/${projectId}`)
}

export async function generateProject(projectId: string): Promise<JobStartResponse> {
  const response = await apiClient.post<JobStartResponse>(`/api/projects/${projectId}/generate`)
  return response.data
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const response = await apiClient.get<JobStatus>(`/api/jobs/${jobId}`)
  return response.data
}

export function buildOutputUrl(projectId: string, outputFormat: 'ifc' | 'dxf' | 'xlsx' | 'svg'): string {
  return `${API_BASE_URL}/api/projects/${projectId}/outputs/${outputFormat}`
}

export function buildJobStreamUrl(jobId: string): string {
  return `${API_WS_BASE_URL}/api/jobs/${jobId}/stream`
}

export function buildChatStreamUrl(projectId: string): string {
  return `${API_WS_BASE_URL}/api/projects/${projectId}/chat/stream`
}