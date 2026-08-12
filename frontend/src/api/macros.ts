import http from './http'

export interface Macro {
  id: number
  project_id: number
  unique_id: string
  name: string
  file_path: string
  description: string
  macro_sql: string
}

export const listMacros = (projectId: number) =>
  http.get<Macro[]>(`/projects/${projectId}/macros`)

export const createMacro = (
  projectId: number,
  data: { name: string; sql: string; subdir?: string },
) => http.post<Macro>(`/projects/${projectId}/macros`, data)

export interface MacroSql {
  macro_id: number
  name: string
  file_path: string
  sql: string
}

export const getMacroSql = (projectId: number, macroId: number) =>
  http.get<MacroSql>(`/projects/${projectId}/macros/${macroId}/sql`)

export const updateMacro = (
  projectId: number,
  macroId: number,
  data: { name?: string; sql?: string; description?: string },
) => http.put<Macro>(`/projects/${projectId}/macros/${macroId}`, data)

export const deleteMacro = (projectId: number, macroId: number) =>
  http.delete<{ message: string }>(`/projects/${projectId}/macros/${macroId}`)
