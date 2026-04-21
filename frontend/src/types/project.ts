export type Point2D = {
  x: number
  y: number
}

export type Polygon2D = {
  points: Point2D[]
}

export type RoomType =
  | 'LIVING'
  | 'KITCHEN'
  | 'BEDROOM'
  | 'BATHROOM'
  | 'CORRIDOR'
  | 'STORAGE'
  | 'PARKING'

export type Solar = {
  id: string
  contour: Polygon2D
  north_angle_deg: number
  max_buildable_height_m: number
}

export type Room = {
  type: RoomType
  min_area: number
  min_short_side: number
}

export type Typology = {
  id: string
  name: string
  min_useful_area: number
  max_useful_area: number
  num_bedrooms: number
  num_bathrooms: number
  rooms: Room[]
}

export type TypologyMix = {
  typology_id: string
  count: number
}

export type Program = {
  project_id: string
  num_floors: number
  floor_height_m: number
  typologies: Typology[]
  mix: TypologyMix[]
}

export type GeneratedOutput = {
  id: string
  output_type: string
  file_path: string
  media_type: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export type SolutionMetrics = {
  total_assigned_area: number
  num_units_placed: number
  typology_fulfillment: Record<string, number>
}

export type UnitPlacement = {
  typology_id: string
  floor: number
  bbox: {
    x: number
    y: number
    width: number
    height: number
  }
}

export type Solution = {
  status: string
  placements: UnitPlacement[]
  communication_cores: Array<{
    position: Point2D
    width_m: number
    depth_m: number
    has_elevator: boolean
    serves_floors: number[]
  }>
  metrics: SolutionMetrics
  solver_time_seconds: number
  message?: string | null
}

export type ProjectVersion = {
  id: string
  version_number: number
  solar: Solar
  program: Program
  solution: Solution | null
  generated_outputs: GeneratedOutput[]
  created_at: string
  updated_at: string
}

export type ProjectSummary = {
  id: string
  name: string
  description: string | null
  latest_version_number: number | null
  status: string
  created_at: string
  updated_at: string
}

export type ProjectDetail = ProjectSummary & {
  current_version: ProjectVersion | null
}

export type ProjectPayload = {
  name: string
  description?: string | null
  solar: Solar
  program: Program
}

export type JobEvent = {
  event: string
  job_id: string
  timestamp: string
  data: Record<string, unknown>
}

export type JobStatus = {
  job_id: string
  project_id: string
  version_id: string
  status: string
  output_formats: string[]
  error: { code: string; message: string } | null
  events: JobEvent[]
}

export type JobStartResponse = {
  job_id: string
  status: string
  project_id: string
}

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  feasible?: boolean
  solution?: Record<string, unknown> | null
}

export type ChatNodeEvent = {
  type: 'node_start' | 'node_end'
  node: string
  label?: string
}

export type ChatDoneEvent = {
  type: 'done'
  response: string
  feasible: boolean
  solution: Record<string, unknown> | null
}

export type ChatErrorEvent = {
  type: 'error'
  message: string
}

export type ChatStreamEvent = ChatNodeEvent | ChatDoneEvent | ChatErrorEvent