"use client";

import { useParams } from "next/navigation";
import { useApi } from "@/lib/use-api";
import { Loading, ErrorBanner, Forbidden, EmptyState } from "@/components/StatusStates";
import DriverBars from "@/components/DriverBars";
import { parseDriversFromNotes, parseConfidenceFromNotes } from "@/lib/parse-drivers";
import type { PatientSummary } from "@/lib/api";

const MODEL_CARD_PATH: Record<string, string> = {
  "readmission-v1": "docs/model_cards/readmission.md",
  "los-v1": "docs/model_cards/los.md",
  "noshow-v1": "docs/model_cards/noshow.md",
};

export default function PatientDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, loading, error, forbidden } = useApi<PatientSummary>(`/v1/patients/${params.id}/summary`);

  return (
    <div>
      <h1 className="page-title">Patient {params.id}</h1>
      <p className="page-subtitle">Demographics, intake summary, and risk scores with drivers.</p>

      {forbidden && <Forbidden requiredRoles="clinician, nurse, admin" />}
      {error && <ErrorBanner message={error} />}
      {loading && <Loading />}

      {!loading && data && (
        <>
          <div className="card">
            <h2>Demographics</h2>
            <table>
              <tbody>
                <tr>
                  <td style={{ width: 140, color: "var(--text-muted)" }}>Name</td>
                  <td>{data.name || "—"}</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--text-muted)" }}>Gender</td>
                  <td>{data.gender || "—"}</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--text-muted)" }}>Birth date</td>
                  <td>{data.birth_date || "—"}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Intake summary (in the patient&apos;s own words)</h2>
            {data.latest_intake_summary ? (
              <table>
                <tbody>
                  {Object.entries(data.latest_intake_summary).map(([key, value]) => (
                    <tr key={key}>
                      <td style={{ width: 160, color: "var(--text-muted)" }}>{key.replace(/_/g, " ")}</td>
                      <td>{value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState text="No intake questionnaire on file for this patient yet." />
            )}
          </div>

          <div className="card">
            <h2>Risk scores</h2>
            {data.risk_assessments.length === 0 && (
              <EmptyState text="No RiskAssessments on file. Score this patient via POST /v1/risk/{model}/score." />
            )}
            {data.risk_assessments.map((ra, i) => {
              const drivers = parseDriversFromNotes(ra.notes);
              const confidence = parseConfidenceFromNotes(ra.notes);
              const modelCard = ra.model ? MODEL_CARD_PATH[ra.model] : null;
              return (
                <div key={i} style={{ marginBottom: 24, paddingBottom: 24, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
                    <strong>
                      {ra.model} {ra.probability !== null ? `— ${(ra.probability * 100).toFixed(1)}%` : ""}
                    </strong>
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {ra.occurrence ? new Date(ra.occurrence).toLocaleString() : ""}
                    </span>
                  </div>
                  <DriverBars drivers={drivers} />
                  {confidence && (
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>{confidence}</p>
                  )}
                  {modelCard && (
                    <p style={{ fontSize: 12, marginTop: 4 }}>
                      Why this score? See <code>{modelCard}</code> for the full model card (baseline, calibration,
                      subgroup fairness report).
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
