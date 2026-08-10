import http from './http'

// 表/视图信息
export interface TableInfo {
  schema: string
  name: string
}

// 数据预览结果
export interface DataPreview {
  columns: string[]
  rows: Record<string, any>[]
  total: number
  returned: number
}

// DDL 结果
export interface DdlResult {
  ddl: string
  type: 'table' | 'view'
}

// 获取数据库列表
export function listDatabases(projectId: number) {
  return http.get<{ databases: string[] }>(
    `/projects/${projectId}/data-viewer/databases`,
  )
}

// 获取表/视图列表
export function listTables(
  projectId: number,
  database: string,
  type: 'table' | 'view',
) {
  return http.get<{ tables: TableInfo[] }>(
    `/projects/${projectId}/data-viewer/tables`,
    { params: { database, type } },
  )
}

// 获取 DDL
export function getDdl(
  projectId: number,
  database: string,
  table: string,
  schema = 'dbo',
) {
  return http.get<DdlResult>(`/projects/${projectId}/data-viewer/ddl`, {
    params: { database, table, schema },
  })
}

// 获取数据预览
export function getData(
  projectId: number,
  database: string,
  table: string,
  schema = 'dbo',
  limit = 1000,
) {
  return http.get<DataPreview>(`/projects/${projectId}/data-viewer/data`, {
    params: { database, table, schema, limit },
  })
}
