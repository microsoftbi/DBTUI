import http from './http'

export interface Model {
  id: number
  project_id: number
  unique_id: string
  name: string
  resource_type: string
  file_path: string
  materialized: string
  database: string
  schema_name: string
  alias: string
  tags_json: string
  description: string
  compiled_code: string
  run_status: string
  run_at: string | null
}

export const listModels = (projectId: number) =>
  http.get<Model[]>(`/projects/${projectId}/models`)

export const createModel = (
  projectId: number,
  data: { name: string; sql: string; subdir?: string },
) => http.post<Model>(`/projects/${projectId}/models`, data)

export const updateModel = (
  projectId: number,
  modelId: number,
  data: { name?: string; sql?: string; materialized?: string },
) => http.put<Model>(`/projects/${projectId}/models/${modelId}`, data)

export const deleteModel = (projectId: number, modelId: number) =>
  http.delete<{ message: string }>(`/projects/${projectId}/models/${modelId}`)

export interface ModelSql {
  model_id: number
  name: string
  file_path: string
  materialized: string
  sql: string
}

export const getModelSql = (projectId: number, modelId: number) =>
  http.get<ModelSql>(`/projects/${projectId}/models/${modelId}/sql`)
