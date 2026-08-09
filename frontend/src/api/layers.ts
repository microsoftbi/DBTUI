import http from './http'

export interface LayerDefinition {
  name: string
  display_name: string
  database: string
  schema: string
  materialized: string
  is_root: boolean
}

export const listLayers = (projectId: number) =>
  http.get<LayerDefinition[]>(`/projects/${projectId}/layers`)

export const getLayer = (projectId: number, layerName: string) =>
  http.get<LayerDefinition>(`/projects/${projectId}/layers/${layerName}`)

export const createLayer = (
  projectId: number,
  data: {
    name: string
    display_name: string
    database: string
    schema: string
    materialized: string
  },
) => http.post<LayerDefinition>(`/projects/${projectId}/layers`, data)

export const updateLayer = (
  projectId: number,
  layerName: string,
  data: {
    name?: string
    display_name?: string
    database?: string
    schema?: string
    materialized?: string
  },
) => http.put<LayerDefinition>(`/projects/${projectId}/layers/${layerName}`, data)

export const deleteLayer = (projectId: number, layerName: string) =>
  http.delete<{ message: string }>(`/projects/${projectId}/layers/${layerName}`)
