import http from './http'

export interface SourceTable {
  name: string
  identifier: string
  description: string
}

export interface SourceDefinition {
  source_name: string
  database: string
  schema: string
  loader: string
  description: string
  tables: SourceTable[]
  subdir: string
}

export const listSources = (projectId: number) =>
  http.get<SourceDefinition[]>(`/projects/${projectId}/sources`)

export const getSource = (projectId: number, sourceName: string) =>
  http.get<SourceDefinition>(`/projects/${projectId}/sources/${sourceName}`)

export const createSource = (
  projectId: number,
  data: {
    source_name: string
    database: string
    schema: string
    loader: string
    description: string
    tables?: SourceTable[]
    subdir?: string
  },
) => http.post<SourceDefinition>(`/projects/${projectId}/sources`, data)

export const updateSource = (
  projectId: number,
  sourceName: string,
  data: {
    source_name?: string
    database?: string
    schema?: string
    loader?: string
    description?: string
    subdir?: string
  },
) => http.put<SourceDefinition>(`/projects/${projectId}/sources/${sourceName}`, data)

export const deleteSource = (projectId: number, sourceName: string) =>
  http.delete<{ message: string }>(`/projects/${projectId}/sources/${sourceName}`)

// ---------- 表管理 ----------
export const addSourceTable = (
  projectId: number,
  sourceName: string,
  data: { name: string; identifier: string; description: string },
) =>
  http.post<SourceDefinition>(
    `/projects/${projectId}/sources/${sourceName}/tables`,
    data,
  )

export const updateSourceTable = (
  projectId: number,
  sourceName: string,
  tableName: string,
  data: { name?: string; identifier?: string; description?: string },
) =>
  http.put<SourceDefinition>(
    `/projects/${projectId}/sources/${sourceName}/tables/${tableName}`,
    data,
  )

export const deleteSourceTable = (
  projectId: number,
  sourceName: string,
  tableName: string,
) =>
  http.delete<SourceDefinition>(
    `/projects/${projectId}/sources/${sourceName}/tables/${tableName}`,
  )
