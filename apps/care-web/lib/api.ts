// API client for the CareFlow FastAPI backend (apps/api). Role is sent as
// an X-Role header -- the backend has no real authentication (see
// apps/api/dependencies.py's own docstring), so this dashboard's role
// switcher is a demo convenience mirroring that, not a login system.

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type Role = "clinician" | "nurse" | "admin" | "auditor" | "system" | "patient";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  role: Role,
  options: RequestInit = {}
): Promise<T> {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "X-Role": role,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch {
      // response body wasn't JSON -- fall back to statusText
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json();
}

export interface PatientRow {
  patient_id: string;
  risk_assessment_id: string;
  model: string;
  probability: number;
  risk_tier: "high" | "medium" | "low";
  occurrence: string;
}

export interface RiskAssessmentSummary {
  model: string;
  probability: number | null;
  occurrence: string | null;
  notes: string[];
}

export interface PatientSummary {
  patient_id: string;
  name: string | null;
  gender: string | null;
  birth_date: string | null;
  latest_intake_summary: Record<string, string> | null;
  risk_assessments: RiskAssessmentSummary[];
  role: string;
}

export interface Escalation {
  audit_id: number;
  timestamp: string;
  thread_id: string;
  patient_id: string;
  reason: string | null;
  transcript_excerpt: { role: string; text: string }[];
}

export interface AuditEvent {
  id: number;
  timestamp: string;
  actor: string;
  actor_role: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  result: string;
  reason: string | null;
}

export interface EvalRun {
  id: number;
  ts: string;
  eval_set: string;
  total: number;
  passed: number;
  pass_rate: number;
  gate: number | null;
  gate_met: boolean | null;
}

export interface QaOverview {
  total_scored: number;
  safety_fail_count: number;
  privacy_fail_count: number;
  avg_accuracy: number | null;
  avg_grounding: number | null;
  avg_tone_and_empathy: number | null;
  avg_language_quality: number | null;
  failure_tag_counts: Record<string, number>;
  recent_eval_runs: EvalRun[];
  role: string;
}

export interface ExperimentReport {
  experiment_id: string;
  generated_at: number;
  report_markdown: string;
  role: string;
}

export interface ChainStatus {
  ok: boolean;
  checked: number;
  first_bad_id: number | null;
}

// Claims pre-check agent (SPEC section 10 stretch module). claims/schema.py
// is the source of truth for these field shapes and the service catalog --
// kept in sync by hand since there's no shared schema generation between
// the Python backend and this TypeScript client.
export interface ClaimLineInput {
  line_id: string;
  service_type: string;
  diagnosis_code: string;
  procedure_code: string;
  amount_aed: number;
  encounter_documentation: string;
  session_number?: number | null;
}

export interface DraftClaimInput {
  claim_id: string;
  patient_id: string;
  practitioner_id: string;
  plan_name: string;
  policy_start_date: string;
  service_date: string;
  pre_authorization_obtained: boolean;
  lines: ClaimLineInput[];
}

export interface ClaimFlag {
  flag_type: string;
  severity: "high" | "medium" | "low";
  reason: string;
  evidence: string;
  citation: string | null;
  line_id: string | null;
}

export interface ClaimPrecheckResult {
  claim_id: string;
  clean: boolean;
  flags: ClaimFlag[];
}

export interface ClaimDecision {
  id: number;
  ts: string;
  claim_id: string;
  flag_type: string;
  line_id: string | null;
  decision: string;
  coder_id: string;
  note: string | null;
}
