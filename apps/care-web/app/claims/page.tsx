"use client";

import { useState } from "react";
import { useRole } from "@/lib/role-context";
import { useApi } from "@/lib/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import type { ClaimPrecheckResult, ClaimDecision, DraftClaimInput } from "@/lib/api";
import { Loading, ErrorBanner, Forbidden, EmptyState } from "@/components/StatusStates";
import { VALID_PLANS, SERVICE_TYPES, EXAMPLE_DIAGNOSIS_CODES, DECISIONS } from "@/lib/claims-catalog";

const EMPTY_FORM = {
  claimId: "demo-claim-1",
  patientId: "demo-patient-1",
  practitionerId: "demo-practitioner-1",
  planName: VALID_PLANS[0],
  policyStartDate: "2024-01-01",
  serviceDate: "2026-01-01",
  preauthObtained: false,
  serviceType: SERVICE_TYPES[0],
  diagnosisCode: EXAMPLE_DIAGNOSIS_CODES[SERVICE_TYPES[0]],
  procedureCode: "PRC0001",
  amountAed: "250",
  documentation: "",
  sessionNumber: "",
  coderId: "care-web-demo-coder",
};

export default function ClaimsPage() {
  const { role } = useRole();
  const [form, setForm] = useState(EMPTY_FORM);
  const [result, setResult] = useState<ClaimPrecheckResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data: decisionsData, forbidden: decisionsForbidden, refetch: refetchDecisions } = useApi<{
    decisions: ClaimDecision[];
  }>("/v1/claims/decisions");

  if (role !== "admin") {
    return (
      <div>
        <h1 className="page-title">Claims pre-check</h1>
        <Forbidden requiredRoles="admin" />
      </div>
    );
  }

  async function runPrecheck(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);

    const draft: DraftClaimInput = {
      claim_id: form.claimId,
      patient_id: form.patientId,
      practitioner_id: form.practitionerId,
      plan_name: form.planName,
      policy_start_date: form.policyStartDate,
      service_date: form.serviceDate,
      pre_authorization_obtained: form.preauthObtained,
      lines: [
        {
          line_id: "L1",
          service_type: form.serviceType,
          diagnosis_code: form.diagnosisCode,
          procedure_code: form.procedureCode,
          amount_aed: parseFloat(form.amountAed) || 0,
          encounter_documentation: form.documentation,
          session_number: form.sessionNumber ? parseInt(form.sessionNumber, 10) : null,
        },
      ],
    };

    try {
      const precheck = await apiFetch<ClaimPrecheckResult>("/v1/claims/precheck", role, {
        method: "POST",
        body: JSON.stringify(draft),
      });
      setResult(precheck);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  async function decide(flagType: string, lineId: string | null, decision: string) {
    if (!result) return;
    try {
      await apiFetch("/v1/claims/decisions", role, {
        method: "POST",
        body: JSON.stringify({
          claim_id: result.claim_id,
          flag_type: flagType,
          line_id: lineId,
          decision,
          coder_id: form.coderId,
        }),
      });
      refetchDecisions();
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  return (
    <div>
      <h1 className="page-title">Claims pre-check</h1>
      <p className="page-subtitle">
        SPEC section 10 stretch module: reviews a draft claim for coding, coverage and completeness problems
        before submission. Every flag is a suggestion for a human coder -- this never changes a claim, and
        every decision below is itself an audited action. Demonstration only: detection of synthetic injected
        problems, not real-world denial prediction (see <code>docs/claims_eval_report.md</code>).
      </p>

      <div className="card">
        <h2>Draft claim</h2>
        <form onSubmit={runPrecheck} className="claims-form">
          <div className="claims-form-grid">
            <label>
              Claim ID
              <input value={form.claimId} onChange={(e) => setForm({ ...form, claimId: e.target.value })} />
            </label>
            <label>
              Patient ID
              <input value={form.patientId} onChange={(e) => setForm({ ...form, patientId: e.target.value })} />
            </label>
            <label>
              Practitioner ID
              <input
                value={form.practitionerId}
                onChange={(e) => setForm({ ...form, practitionerId: e.target.value })}
              />
            </label>
            <label>
              Plan
              <select value={form.planName} onChange={(e) => setForm({ ...form, planName: e.target.value })}>
                {VALID_PLANS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Policy start date
              <input
                type="date"
                value={form.policyStartDate}
                onChange={(e) => setForm({ ...form, policyStartDate: e.target.value })}
              />
            </label>
            <label>
              Service date
              <input
                type="date"
                value={form.serviceDate}
                onChange={(e) => setForm({ ...form, serviceDate: e.target.value })}
              />
            </label>
            <label>
              Service type
              <select
                value={form.serviceType}
                onChange={(e) =>
                  setForm({
                    ...form,
                    serviceType: e.target.value,
                    diagnosisCode: EXAMPLE_DIAGNOSIS_CODES[e.target.value] || form.diagnosisCode,
                  })
                }
              >
                {SERVICE_TYPES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Diagnosis code (ICD-10)
              <input
                value={form.diagnosisCode}
                onChange={(e) => setForm({ ...form, diagnosisCode: e.target.value })}
              />
            </label>
            <label>
              Procedure code
              <input value={form.procedureCode} onChange={(e) => setForm({ ...form, procedureCode: e.target.value })} />
            </label>
            <label>
              Amount (AED)
              <input value={form.amountAed} onChange={(e) => setForm({ ...form, amountAed: e.target.value })} />
            </label>
            {form.serviceType === "physiotherapy_session" && (
              <label>
                Session number (this year)
                <input
                  value={form.sessionNumber}
                  onChange={(e) => setForm({ ...form, sessionNumber: e.target.value })}
                />
              </label>
            )}
            <label className="claims-form-checkbox">
              <input
                type="checkbox"
                checked={form.preauthObtained}
                onChange={(e) => setForm({ ...form, preauthObtained: e.target.checked })}
              />
              Pre-authorisation obtained
            </label>
          </div>
          <label className="claims-form-full">
            Encounter documentation
            <textarea
              value={form.documentation}
              onChange={(e) => setForm({ ...form, documentation: e.target.value })}
              rows={2}
              placeholder="What the clinician wrote about this visit..."
            />
          </label>
          <label className="claims-form-full">
            Coder ID (used when recording a decision below)
            <input value={form.coderId} onChange={(e) => setForm({ ...form, coderId: e.target.value })} />
          </label>

          <button type="submit" className="button-link" disabled={submitting}>
            {submitting ? "Running..." : "Run pre-check"}
          </button>
        </form>
      </div>

      {submitError && <ErrorBanner message={submitError} />}

      {result && (
        <div className="card">
          <h2>
            Result:{" "}
            <span className={result.clean ? "badge badge-ok" : "badge badge-fail"}>
              {result.clean ? "clean" : `${result.flags.length} flag(s)`}
            </span>
          </h2>
          {result.clean && <EmptyState text="No flags raised for this draft claim." />}
          {result.flags.map((flag, i) => (
            <div className="escalation-item" key={i}>
              <div className="meta">
                <span className={`badge badge-${flag.severity}`}>{flag.severity}</span>{" "}
                <strong>{flag.flag_type}</strong>
                {flag.line_id && <> · line {flag.line_id}</>}
              </div>
              <p style={{ margin: "0 0 6px" }}>{flag.reason}</p>
              <p style={{ margin: "0 0 6px", color: "var(--text-muted)", fontSize: 13 }}>
                Evidence: {flag.evidence}
                {flag.citation && <> · Source: {flag.citation}</>}
              </p>
              <div className="claims-decision-buttons">
                {DECISIONS.map((d) => (
                  <button
                    key={d}
                    type="button"
                    className="button-link"
                    onClick={() => decide(flag.flag_type, flag.line_id, d)}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2>Recent decisions</h2>
        {decisionsForbidden && <Forbidden requiredRoles="admin" />}
        {decisionsData && decisionsData.decisions.length === 0 && (
          <EmptyState text="No coder decisions recorded yet." />
        )}
        {decisionsData && decisionsData.decisions.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Claim</th>
                <th>Flag</th>
                <th>Decision</th>
                <th>Coder</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {decisionsData.decisions.map((d) => (
                <tr key={d.id}>
                  <td>{new Date(d.ts).toLocaleString()}</td>
                  <td>{d.claim_id}</td>
                  <td>{d.flag_type}</td>
                  <td>{d.decision}</td>
                  <td>{d.coder_id}</td>
                  <td>{d.note || "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!decisionsData && !decisionsForbidden && <Loading />}
      </div>
    </div>
  );
}
