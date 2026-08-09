import http from './http'

export interface DagNode {
  id: string
  label: string
  type: string
  status: string
  materialized?: string | null
  run_at?: string | null
}

export interface DagEdge {
  source: string
  target: string
}

export interface Dag {
  nodes: DagNode[]
  edges: DagEdge[]
}

export const getDag = (projectId: number) =>
  http.get<Dag>(`/projects/${projectId}/dag`)
