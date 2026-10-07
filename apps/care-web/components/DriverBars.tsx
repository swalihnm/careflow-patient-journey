import type { ParsedDriver } from "@/lib/parse-drivers";

export default function DriverBars({ drivers }: { drivers: ParsedDriver[] }) {
  if (drivers.length === 0) {
    return <p className="empty-state">No driver breakdown available for this score.</p>;
  }
  const maxAbsShap = Math.max(...drivers.map((d) => Math.abs(d.shap)), 0.001);

  return (
    <div>
      {drivers.map((d) => (
        <div className="driver-bar-row" key={d.feature}>
          <div className="driver-label" title={d.feature}>
            {d.feature}
          </div>
          <div className="driver-bar-track">
            <div
              className={`driver-bar-fill ${d.direction === "increases" ? "increase" : "decrease"}`}
              style={{ width: `${(Math.abs(d.shap) / maxAbsShap) * 100}%` }}
            />
          </div>
          <div style={{ fontSize: 12, width: 220, flexShrink: 0, color: "var(--text-muted)" }}>
            {d.value} · {d.direction} risk
          </div>
        </div>
      ))}
    </div>
  );
}
