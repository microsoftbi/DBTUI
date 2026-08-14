import http from './http'

export interface Snapshot {
  id: number
  project_id: number
  unique_id: string
  name: string
  resource_type: string
  file_path: string
  database: string
  schema_name: string
  alias: string
  tags_json: string
  description: string
  compiled_code: string
  snapshot_strategy: string
  target_schema: string
  unique_key: string
  run_status: string
  run_at: string | null
}

export const listSnapshots = (projectId: number) =>
  http.get<Snapshot[]>(`/projects/${projectId}/snapshots`)

export const createSnapshot = (
  projectId: number,
  data: { name: string; sql: string },
) => http.post<Snapshot>(`/projects/${projectId}/snapshots`, data)

export const updateSnapshot = (
  projectId: number,
  snapshotId: number,
  data: { name?: string; sql?: string },
) => http.put<Snapshot>(`/projects/${projectId}/snapshots/${snapshotId}`, data)

export const deleteSnapshot = (projectId: number, snapshotId: number) =>
  http.delete<{ message: string }>(`/projects/${projectId}/snapshots/${snapshotId}`)

export interface SnapshotSql {
  snapshot_id: number
  name: string
  file_path: string
  sql: string
}

export const getSnapshotSql = (projectId: number, snapshotId: number) =>
  http.get<SnapshotSql>(`/projects/${projectId}/snapshots/${snapshotId}/sql`)
