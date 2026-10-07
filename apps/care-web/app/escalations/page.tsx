"use client";

import { useApi } from "@/lib/use-api";
import { Loading, ErrorBanner, Forbidden, EmptyState } from "@/components/StatusStates";
import type { Escalation } from "@/lib/api";

export default function EscalationsPage() {
  const { data, loading, error, forbidden } = useApi<{ escalations: Escalation[] }>("/v1/escalations");

  return (
    <div>
      <h1 className="page-title">Escalations</h1>
      <p className="page-subtitle">
        Every red-flag escalation the assistant has raised, with the reason and the last few turns of the
        conversation that triggered it. Every escalation here is already an audited event (see{" "}
        <a href="/audit">Audit</a>) -- this view and the audit log read from the same source, not two tables
        that could drift apart.
      </p>

      {forbidden && <Forbidden requiredRoles="nurse, clinician, admin" />}
      {error && <ErrorBanner message={error} />}
      {loading && <Loading />}

      {!loading && data && data.escalations.length === 0 && (
        <div className="card">
          <EmptyState text="No escalations recorded yet." />
        </div>
      )}

      {!loading &&
        data &&
        data.escalations.map((esc) => (
          <div className="escalation-item" key={esc.audit_id}>
            <div className="meta">
              {new Date(esc.timestamp).toLocaleString()} · patient <strong>{esc.patient_id}</strong> · thread{" "}
              {esc.thread_id}
            </div>
            <p style={{ margin: "0 0 10px" }}>
              <strong>Reason:</strong> {esc.reason || "(no reason recorded)"}
            </p>
            {esc.transcript_excerpt.length > 0 && (
              <div className="transcript-excerpt">
                {esc.transcript_excerpt.map((turn, i) => (
                  <div className={`turn ${turn.role}`} key={i}>
                    <strong>{turn.role}:</strong> {turn.text}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
    </div>
  );
}
