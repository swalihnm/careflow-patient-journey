export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface OfferedSlot {
  index: number;
  start: string;
  end: string;
  practitioner_id: string;
}

export interface CancellableAppointment {
  index: number;
  start: string;
  end: string;
}

export interface ChatTurnResult {
  thread_id: string;
  reply: string;
  language: string | null;
  escalated: boolean;
  intent: string | null;
  booking_stage: string | null;
  offered_slots: OfferedSlot[];
  cancel_stage: string | null;
  cancellable_appointments: CancellableAppointment[];
  intake_awaiting: string | null;
}

// POST /v1/chat is a StreamingResponse that emits exactly one
// "data: {...}\n\n" SSE event (see apps/api/routers/chat.py) -- not a
// token-by-token stream. Parsed by reading the whole body rather than
// using EventSource, since EventSource can't send a POST body.
export async function sendChatMessage(
  patientId: string,
  message: string,
  threadId: string | null
): Promise<ChatTurnResult> {
  const resp = await fetch(`${API_BASE_URL}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id: patientId, message, thread_id: threadId }),
  });
  if (!resp.ok) {
    throw new Error(`Chat request failed: ${resp.status}`);
  }
  const text = await resp.text();
  const match = text.match(/^data: (.+)$/m);
  if (!match) {
    throw new Error("Unexpected chat response format");
  }
  return JSON.parse(match[1]);
}

export type ConsentCategory = "ai-intake" | "hie-share";

export class PatientNotFoundError extends Error {}

export async function setConsent(
  patientId: string,
  category: ConsentCategory,
  active: boolean
): Promise<{ id: string; status: string; category: string }> {
  const resp = await fetch(`${API_BASE_URL}/v1/consent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id: patientId, category, active }),
  });
  if (resp.status === 404) {
    // This portfolio demo has no patient-registration flow -- a real
    // deployment would have created the Patient record before anyone could
    // reach this screen. Surfaced distinctly so the UI can say so plainly
    // instead of a generic "something went wrong."
    throw new PatientNotFoundError(`Patient '${patientId}' not found`);
  }
  if (!resp.ok) {
    throw new Error(`Consent request failed: ${resp.status}`);
  }
  return resp.json();
}
