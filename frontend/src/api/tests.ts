import http from './http'

export interface Test {
  id: number
  project_id: number
  unique_id: string
  name: string
  type: string
  severity: string
  file_path: string
  tags_json: string
  model_unique_id: string
  run_status: string
  run_at: string | null
}

export const listTests = (projectId: number) =>
  http.get<Test[]>(`/projects/${projectId}/tests`)

export const createTest = (
  projectId: number,
  data: { name: string; sql: string },
) => http.post<Test>(`/projects/${projectId}/tests`, data)

export interface TestSql {
  test_id: number
  name: string
  file_path: string
  type: string
  sql: string
}

export const getTestSql = (projectId: number, testId: number) =>
  http.get<TestSql>(`/projects/${projectId}/tests/${testId}/sql`)

export const deleteTest = (projectId: number, testId: number) =>
  http.delete<{ message: string }>(`/projects/${projectId}/tests/${testId}`)
