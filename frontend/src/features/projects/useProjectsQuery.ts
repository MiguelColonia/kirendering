import { useQuery } from '@tanstack/react-query'
import { getProject, listProjects } from '../../api/projects'

export function useProjectsQuery() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
  })
}

export function useProjectDetailQuery(projectId?: string) {
  return useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId!),
    enabled: Boolean(projectId),
  })
}