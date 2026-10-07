"use client";

import { useApi } from "@/lib/use-api";
import { Loading, ErrorBanner, Forbidden, EmptyState } from "@/components/StatusStates";
import type { QaOverview } from "@/lib/api";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function fmtAvg(v: number | null): string {
  return v === null ? "—" : v.toFixed(2);
}

export default function QualityPage() {
  const { data, loading, error, forbidden } = useApi<QaOverview>("/v1/qa/overview");

  return (
    <div>
      <h1 className="page-title">Quality</h1>
      <p className="page-subtitle">
        QA judge scores across every scored conversation: an independent LLM auditor (different prompt than
        the assistant itself) scoring safety, accuracy, grounding, privacy, tone and language quality. See{" "}
        <code>docs/qa_calibration_demo.md</code> for how well this judge agrees with a human rater (currently a
        scripted-transcript demo, not a live production calibration).
      </p>

      {forbidden && <Forbidden requiredRoles="admin, clinician" />}
      {error && <ErrorBanner message={error} />}
      {loading && <Loading />}

      {!loading && data && (
        <>
          <div className="stat-row">
            <Stat label="Conversations scored" value={String(data.total_scored)} />
            <Stat label="Safety fails" value={String(data.safety_fail_count)} />
            <Stat label="Privacy fails" value={String(data.privacy_fail_count)} />
          </div>

          <div className="card">
            <h2>Average scores (1-5 dimensions)</h2>
            <table>
              <tbody>
                <tr>
                  <td>Accuracy</td>
                  <td>{fmtAvg(data.avg_accuracy)}</td>
                </tr>
                <tr>
                  <td>Grounding</td>
                  <td>{fmtAvg(data.avg_grounding)}</td>
                </tr>
                <tr>
                  <td>Tone &amp; empathy</td>
                  <td>{fmtAvg(data.avg_tone_and_empathy)}</td>
                </tr>
                <tr>
                  <td>Language quality</td>
                  <td>{fmtAvg(data.avg_language_quality)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Top failure tags</h2>
            {Object.keys(data.failure_tag_counts).length === 0 ? (
              <EmptyState text="No failure tags recorded yet." />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Tag</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.failure_tag_counts)
                    .sort((a, b) => b[1] - a[1])
                    .map(([tag, count]) => (
                      <tr key={tag}>
                        <td>{tag}</td>
                        <td>{count}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card">
            <h2>Eval set runs (SPEC 11: nightly live run)</h2>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: -6, marginBottom: 14 }}>
              Safety, scope, prompt-injection and conversation eval sets, recorded by{" "}
              <code>.github/workflows/nightly.yml</code> (or a manual <code>uv run python -m evals.run_all_and_record</code>).
            </p>
            {data.recent_eval_runs.length === 0 ? (
              <EmptyState text="No eval runs recorded yet -- run `uv run python -m evals.run_all_and_record`." />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Eval set</th>
                    <th>When</th>
                    <th>Pass rate</th>
                    <th>Gate</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_eval_runs.map((run) => (
                    <tr key={run.id}>
                      <td>{run.eval_set}</td>
                      <td>{new Date(run.ts).toLocaleString()}</td>
                      <td>
                        {(run.pass_rate * 100).toFixed(1)}% ({run.passed}/{run.total})
                      </td>
                      <td>
                        {run.gate === null ? (
                          "—"
                        ) : (
                          <span className={`badge ${run.gate_met ? "badge-ok" : "badge-fail"}`}>
                            {run.gate_met ? "met" : "missed"} ({(run.gate * 100).toFixed(0)}%)
                          </span>
                        )}
                      </td>
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
