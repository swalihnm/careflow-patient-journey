"use client";

import { useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/use-api";
import { Loading, ErrorBanner, Forbidden, EmptyState } from "@/components/StatusStates";
import type { PatientRow } from "@/lib/api";

function RiskBadge({ tier }: { tier: string }) {
  return <span className={`badge badge-${tier}`}>{tier}</span>;
}

export default function WorklistPage() {
  const [riskTier, setRiskTier] = useState<string>("");
  const path = `/v1/patients${riskTier ? `?risk_tier=${riskTier}` : ""}`;
  const { data, loading, error, forbidden } = useApi<{ patients: PatientRow[] }>(path, [riskTier]);

  return (
    <div>
      <h1 className="page-title">Worklist</h1>
      <p className="page-subtitle">
        Patients with a recorded risk score, sorted highest risk first. Open escalations are tracked separately
        on the <Link href="/escalations">Escalations</Link> page.
      </p>

      {forbidden && <Forbidden requiredRoles="clinician, nurse, admin" />}
      {error && <ErrorBanner message={error} />}

      {!forbidden && (
        <div className="card">
          <div className="filters">
            <select value={riskTier} onChange={(e) => setRiskTier(e.target.value)}>
              <option value="">All risk tiers</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {loading && <Loading />}
          {!loading && data && data.patients.length === 0 && (
            <EmptyState text="No RiskAssessments found for this filter. Score a patient via POST /v1/risk/{model}/score first." />
          )}
          {!loading && data && data.patients.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Model</th>
                  <th>Risk tier</th>
                  <th>Probability</th>
                  <th>Scored at</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.patients.map((p) => (
                  <tr key={p.risk_assessment_id}>
                    <td>{p.patient_id}</td>
                    <td>{p.model}</td>
                    <td>
                      <RiskBadge tier={p.risk_tier} />
                    </td>
                    <td>{(p.probability * 100).toFixed(1)}%</td>
                    <td>{p.occurrence ? new Date(p.occurrence).toLocaleString() : "—"}</td>
                    <td>
                      <Link href={`/patients/${p.patient_id}`}>View detail →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
