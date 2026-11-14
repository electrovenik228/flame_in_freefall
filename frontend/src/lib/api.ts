export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export type Params = Record<string, string | number | boolean | null | undefined>;

export function apiUrl(path: string, params?: Params): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString();
  return `/api/v1${path}${suffix ? `?${suffix}` : ""}`;
}

export async function api<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path, params), { credentials: "same-origin", ...init });
  if (!response.ok) {
    let code = "error";
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      /* keep the default message */
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type Pillar = "prevention" | "detection" | "suppression";

export interface InvestigationListItem {
  psi_id: string;
  acronym: string;
  title: string;
  display_name: string;
  doi: string;
  project: string | null;
  research_area: string;
  sub_research_area: string;
  project_type: string;
  start_date: string | null;
  end_date: string | null;
  objectives: string;
  fuel_state: "" | "gas" | "liquid" | "solid";
  safety_pillars: Pillar[];
  data_depth: "" | "per_test" | "telemetry" | "summary" | "qualitative";
  oxygen_pct_min: number | null;
  oxygen_pct_max: number | null;
  pressure_kpa_min: number | null;
  pressure_kpa_max: number | null;
  flow_speed_cm_s_min: number | null;
  flow_speed_cm_s_max: number | null;
  conditions_source: "" | "test_runs" | "record_text" | "not_available";
  test_run_count: number;
  facilities: string[];
  is_seed: boolean;
  psi_url: string;
}

export interface Facility {
  id: number;
  name: string;
  type: string;
  description: string;
  url: string;
}

export interface Publication {
  id: number;
  psi_id: string;
  title: string;
  authors: string;
  year: number | null;
  doi: string;
  url: string;
}

export interface VariableEntry {
  field: string;
  label: string;
  unit?: string | null;
  recorded_runs?: number;
  distinct_values?: number;
  min?: number;
  max?: number;
  values?: string[];
}

export interface Citation {
  n: number;
  psi_id: string;
  document_title: string;
  document_kind: string;
  psi_url: string;
  cited_text: string;
}

export interface Segment {
  text: string;
  citations: number[];
}

export interface AiBlock<T> {
  content: T;
  citations: Citation[];
  model: string;
  generated_at: string;
  review_status: string;
  prompt_version: string;
  checks: Record<string, unknown>;
}

export interface SummaryContent {
  plain: Segment[];
  expert: Segment[];
}

export interface InvestigationDetail extends Omit<InvestigationListItem, "facilities"> {
  approach: string;
  hypothesis: string;
  benefits: string;
  flight_program: string;
  hardware_text: string;
  hardware_links: string[];
  contacts: { name: string; affiliation: string; roles: string[] }[];
  license_name: string;
  license_url: string;
  psi_version: number | null;
  total_file_size: number | null;
  retrieved_at: string | null;
  judgment_scores: Record<string, { score: number; rationale: string; evidence?: { quote: string }[] }>;
  facilities: Facility[];
  instruments: { id: number; name: string; measurement_type: string }[];
  publications: Publication[];
  variables: {
    test_run_count: number;
    varied: VariableEntry[];
    constant: VariableEntry[];
    not_recorded: VariableEntry[];
  };
  summary: AiBlock<SummaryContent> | null;
  extraction: AiBlock<Record<string, unknown>> | null;
  related: { psi_id: string; display_name: string; title: string }[];
  file_count: number;
}

export interface TestRun {
  id: number;
  psi_id: string;
  investigation_name: string;
  test_label: string;
  date: string | null;
  fuel: string;
  fuel_form: string;
  geometry: string;
  oxygen_pct: number | null;
  diluent: string;
  pressure_kpa: number | null;
  flow_speed_cm_s: number | null;
  flow_direction: string;
  gravity_level: string;
  ignited: boolean | null;
  extinction_mode: string;
  source_file: string;
  source_row: number;
}

export interface Stats {
  investigations: number;
  seed_investigations: number;
  test_runs: number;
  investigations_with_test_runs: number;
  publications: number;
  facilities: number;
  safety_pillars: Record<Pillar, number>;
  fuel_states: Record<string, number>;
  last_refresh: string | null;
  source_retrieved_at: string | null;
}
