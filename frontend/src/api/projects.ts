import http from './http'
import type { Project } from '@/types'

export const listProjects = () => http.get<Project[]>('/projects')

export const createProject = (data: { name: string; adapter: string; description?: string }) =>
  http.post<Project>('/projects', data)

export const updateProject = (id: number, data: Partial<Project>) =>
  http.patch<Project>(`/projects/${id}`, data)

export const deleteProject = (id: number) =>
  http.delete<{ message: string }>(`/projects/${id}`)

export const parseProject = (id: number) =>
  http.post<Project>(`/projects/${id}/parse`)

export const getProfiles = (id: number) =>
  http.get<{ content: string }>(`/projects/${id}/profiles`)

export const saveProfiles = (id: number, content: string) =>
  http.put<{ message: string }>(`/projects/${id}/profiles`, { content })
