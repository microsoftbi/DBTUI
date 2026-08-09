import http from './http'

export interface RunHistory {
  id: number
  project_id: number
  run_type: string
  selection: string
  status: string
  started_at: string | null
  finished_at: string | null
}

export interface RunResult {
  id: number
  run_id: number
  unique_id: string
  status: string
  message: string
  execution_time: number
}

export const listRuns = (projectId: number) =>
  http.get<RunHistory[]>(`/projects/${projectId}/runs`)

export const getRunDetail = (projectId: number, runId: number) =>
  http.get<{ run: RunHistory; results: RunResult[]; log: string }>(
    `/projects/${projectId}/runs/${runId}`,
  )

export const cancelRun = (projectId: number, runId: number) =>
  http.post<{ message: string }>(`/projects/${projectId}/runs/${runId}/cancel`)
