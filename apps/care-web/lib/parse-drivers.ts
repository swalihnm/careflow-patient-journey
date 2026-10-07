// ml/features_fhir.py's build_risk_assessment()/build_los_risk_assessment()
// write drivers only as a fixed-format sentence in a FHIR RiskAssessment's
// `note` array (there's no structured FHIR extension per driver, only for
// the overall confidence score) -- e.g.
// "Top drivers: age_midpoint=46.4 decreases risk (SHAP -0.388); number_inpatient=0 decreases risk (SHAP -0.163)"
// Parsed here rather than by changing that FHIR schema, since the format is
// fixed and this is read-only display. If that sentence's format ever
// changes, this parser (and only this parser) needs to change with it.

export interface ParsedDriver {
  feature: string;
  value: string;
  direction: "increases" | "decreases";
  shap: number;
}

const DRIVER_PATTERN = /([\w.]+)=(.+?) (increases|decreases) risk \(SHAP ([+-]?[\d.]+)\)/g;

export function parseDriversFromNotes(notes: string[]): ParsedDriver[] {
  const driverNote = notes.find((n) => n.startsWith("Top drivers:"));
  if (!driverNote) return [];

  const drivers: ParsedDriver[] = [];
  for (const match of driverNote.matchAll(DRIVER_PATTERN)) {
    drivers.push({
      feature: match[1],
      value: match[2],
      direction: match[3] as "increases" | "decreases",
      shap: parseFloat(match[4]),
    });
  }
  return drivers;
}

export function parseConfidenceFromNotes(notes: string[]): string | null {
  return notes.find((n) => n.startsWith("Feature confidence:")) || null;
}
