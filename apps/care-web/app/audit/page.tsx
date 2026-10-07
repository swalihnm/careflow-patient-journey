"use client";

import { useState } from "react";
import { useApi } from "@/lib/use-api";
import { Loading, ErrorBanner, Forbidden, EmptyState } from "@/components/StatusStates";
import type { AuditEvent, ChainStatus } from "@/lib/api";

export default function AuditPage() {
  const [actionFilter, setActionFilter] = useState("");
  const path = `/v1/audit${actionFilter ? `?action=${actionFilter}` : ""}`;
  const { data, loading, error, forbidden } = useApi<{ events: AuditEvent[]; chain_status: ChainStatus }>(
    path,
    [actionFilter]
  );

  return (
    <div>
      <h1 className="page-title">Audit</h1>
      <p className="page-subtitle">
        Every FHIR access, LLM call, escalation and consent change is logged to a tamper-evident hash chain
        (<code>trustcore</code>). The auditor role sees masked actor/resource identifiers, per SPEC&apos;s
        field-masking rules.
      </p>

      {forbidden && <Forbidden requiredRoles="auditor, admin" />}
      {error && <ErrorBanner message={error} />}
      {loading && <Loading />}

      {!loading && data && (
        <>
          <div className="card">
            <h2>Chain status</h2>
            <p>
              <span className={`badge ${data.chain_status.ok ? "badge-ok" : "badge-fail"}`}>
                {data.chain_status.ok ? "Intact" : "Tampered"}
              </span>{" "}
              <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
                {data.chain_status.checked} records checked
                {data.chain_status.first_bad_id !== null && `, first bad record: ${data.chain_status.first_bad_id}`}
              </span>
            </p>
          </div>

          <div className="card">
            <div className="filters">
              <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
                <option value="">All actions</option>
                <option value="escalation">escalation</option>
                <option value="llm_call">llm_call</option>
                <option value="fhir_read">fhir_read</option>
                <option value="write_risk_assessment">write_risk_assessment</option>
                <option value="consent_change">consent_change</option>
              </select>
            </div>

            {data.events.length === 0 ? (
              <EmptyState text="No audit events match this filter." />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Actor</th>
                    <th>Role</th>
                    <th>Action</th>
                    <th>Resource</th>
                    <th>Result</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {data.events.map((event) => (
                    <tr key={event.id}>
                      <td style={{ whiteSpace: "nowrap" }}>{new Date(event.timestamp).toLocaleString()}</td>
                      <td>{event.actor}</td>
                      <td>{event.actor_role}</td>
                      <td>{event.action}</td>
                      <td>
                        {event.resource_type}
                        {event.resource_id ? ` / ${event.resource_id}` : ""}
                      </td>
                      <td>
                        <span className={`badge ${event.result === "allow" ? "badge-ok" : "badge-fail"}`}>
                          {event.result}
                        </span>
                      </td>
                      <td>{event.reason || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
