// Mirrors claims/schema.py's VALID_PLANS and SERVICE_CATALOG -- kept small
// and hand-synced since this is a form-option source, not shared logic (the
// real validation happens server-side in claims/completeness_check.py and
// claims/coverage_check.py; this just keeps the form from offering nonsense).

export const VALID_PLANS = ["Gulf Horizon Standard", "Gulf Horizon Plus", "Gulf Horizon Family"];

export const SERVICE_TYPES = [
  "general_practice_visit",
  "specialist_visit",
  "physiotherapy_session",
  "diagnostic_imaging",
  "mri_ct_scan",
  "maternity_care",
  "dental_care",
  "vision_care",
  "paediatric_visit",
  "cosmetic_procedure",
  "hospital_admission",
  "emergency_care",
];

export const EXAMPLE_DIAGNOSIS_CODES: Record<string, string> = {
  general_practice_visit: "J06.9",
  specialist_visit: "I10",
  physiotherapy_session: "M54.5",
  diagnostic_imaging: "S93.4",
  mri_ct_scan: "M51.2",
  maternity_care: "Z34.0",
  dental_care: "K02.9",
  vision_care: "H52.1",
  paediatric_visit: "Z00.129",
  cosmetic_procedure: "Z41.1",
  hospital_admission: "J18.9",
  emergency_care: "S06.0",
};

export const DECISIONS = ["accept", "override", "dismiss"] as const;
