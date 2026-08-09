export interface Project {
  id: number
  name: string
  slug: string
  path: string
  adapter: string
  description: string
  dbt_version: string
  parse_status: string
  parsed_at: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  adapter: string
  description?: string
}

export interface ProjectUpdate {
  name?: string
  adapter?: string
  description?: string
}
