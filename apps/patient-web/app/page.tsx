"use client";

import { useEffect, useRef, useState } from "react";
import { useSession } from "@/lib/session-context";
import { t } from "@/lib/i18n";
import {
  sendChatMessage,
  setConsent,
  PatientNotFoundError,
  type ChatTurnResult,
  type OfferedSlot,
  type CancellableAppointment,
} from "@/lib/api";
import {
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  startListening,
  speak,
  stopSpeaking,
  type ListeningHandle,
} from "@/lib/speech";

interface Message {
  role: "patient" | "assistant";
  text: string;
  offeredSlots?: OfferedSlot[];
  bookingStage?: string | null;
  cancellableAppointments?: CancellableAppointment[];
  cancelStage?: string | null;
  escalated?: boolean;
}

const WEEKDAYS_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Deliberately NOT using toLocaleString() / Intl, which convert to the
// *browser's* system timezone -- found via a real bug: this UI's cards
// showed a different time than the assistant's own text reply for the
// exact same slot (18:30 vs 13:00), because assistant/booking.py's
// format_time() formats the ISO timestamp's wall-clock fields directly,
// with no timezone conversion, and this must match that exactly, not
// re-interpret the same timestamp through whatever timezone Playwright (or
// a patient's browser) happens to be running in.
function formatTime(iso: string, lang: "en" | "ar"): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  const hh = pad(d.getUTCHours());
  const mm = pad(d.getUTCMinutes());
  if (lang === "ar") {
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${hh}:${mm}`;
  }
  return `${WEEKDAYS_EN[d.getUTCDay()]} ${pad(d.getUTCDate())} ${MONTHS_EN[d.getUTCMonth()]}, ${hh}:${mm}`;
}

export default function PatientChatPage() {
  const session = useSession();
  const [patientIdInput, setPatientIdInput] = useState("");
  const [consenting, setConsenting] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [everEscalated, setEverEscalated] = useState(false);
  const [listening, setListening] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [voiceSupport, setVoiceSupport] = useState({ stt: false, tts: false });
  const scrollRef = useRef<HTMLDivElement>(null);
  const listenHandleRef = useRef<ListeningHandle | null>(null);

  const lang = session.lang;

  useEffect(() => {
    setVoiceSupport({ stt: isSpeechRecognitionSupported(), tts: isSpeechSynthesisSupported() });
  }, []);

  useEffect(() => {
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // "Read replies aloud" (SPEC F8 voice I/O, "Could" priority): speaks the
  // assistant's side only, never the patient's own messages echoed back.
  useEffect(() => {
    if (!autoSpeak) return;
    const last = messages[messages.length - 1];
    if (last && last.role === "assistant") {
      speak(last.text, lang);
    }
  }, [messages, autoSpeak, lang]);

  useEffect(() => {
    return () => {
      listenHandleRef.current?.stop();
      stopSpeaking();
    };
  }, []);

  if (!session.ready) {
    return null;
  }

  function toggleVoiceInput() {
    if (listening) {
      listenHandleRef.current?.stop();
      listenHandleRef.current = null;
      setListening(false);
      return;
    }
    const handle = startListening(
      lang,
      (transcript) => {
        setDraft(transcript);
        setListening(false);
        listenHandleRef.current = null;
      },
      () => {
        setListening(false);
        listenHandleRef.current = null;
      },
      () => {
        setError(t("micError", lang));
        setListening(false);
        listenHandleRef.current = null;
      }
    );
    if (handle) {
      listenHandleRef.current = handle;
      setListening(true);
    }
  }

  function toggleAutoSpeak() {
    if (autoSpeak) stopSpeaking();
    setAutoSpeak((v) => !v);
  }

  async function handleAcceptConsent() {
    if (!session.patientId) return;
    setConsenting(true);
    setError(null);
    try {
      await setConsent(session.patientId, "ai-intake", true);
      session.setConsented(true);
    } catch (err) {
      setError(err instanceof PatientNotFoundError ? t("patientNotFound", lang) : t("errorBanner", lang));
    } finally {
      setConsenting(false);
    }
  }

  function applyResult(result: ChatTurnResult) {
    session.setThreadId(result.thread_id);
    if (result.escalated) setEverEscalated(true);
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        text: result.reply,
        // Only show the picker cards on the turn that's actually offering a
        // choice -- found via a real bug: ConversationState carries
        // offered_slots/cancellable_appointments forward across turns (so
        // the graph still knows what was offered once the patient answers),
        // but echoing that same list back as cards on every later turn too
        // (e.g. once already at "awaiting_confirmation") just redundantly
        // re-renders the same picker under the confirmation prompt.
        offeredSlots:
          result.booking_stage === "slots_offered" && result.offered_slots.length > 0
            ? result.offered_slots
            : undefined,
        bookingStage: result.booking_stage,
        cancellableAppointments:
          result.cancel_stage === "choosing" && result.cancellable_appointments.length > 0
            ? result.cancellable_appointments
            : undefined,
        cancelStage: result.cancel_stage,
        escalated: result.escalated,
      },
    ]);
  }

  async function sendMessage(text: string) {
    if (!session.patientId || !text.trim() || sending) return;
    setMessages((prev) => [...prev, { role: "patient", text }]);
    setDraft("");
    setSending(true);
    setError(null);
    try {
      const result = await sendChatMessage(session.patientId, text, session.threadId);
      applyResult(result);
    } catch {
      setError(t("errorBanner", lang));
    } finally {
      setSending(false);
    }
  }

  // --- Gate 1: patient id (no real login in this portfolio project -- see
  // apps/api/dependencies.py's own docstring for the same design choice on
  // the care-team dashboard) ---
  if (!session.patientId) {
    return (
      <div className="app-container" dir={lang === "ar" ? "rtl" : "ltr"}>
        <div className="gate-screen">
          <h1>
            Care<span style={{ color: "var(--primary)" }}>Flow</span>
          </h1>
          <p>{t("patientIdLabel", lang)}</p>
          <input
            value={patientIdInput}
            onChange={(e) => setPatientIdInput(e.target.value)}
            placeholder={t("patientIdPlaceholder", lang)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && patientIdInput.trim()) session.setPatientId(patientIdInput.trim());
            }}
          />
          <button
            className="primary-button"
            disabled={!patientIdInput.trim()}
            onClick={() => session.setPatientId(patientIdInput.trim())}
          >
            {t("continueButton", lang)}
          </button>
          <button className="secondary-button" onClick={() => session.setLang(lang === "ar" ? "en" : "ar")}>
            {t("languageToggle", lang)}
          </button>
        </div>
      </div>
    );
  }

  // --- Gate 2: consent screen on first use (SPEC 9) ---
  if (!session.consented) {
    return (
      <div className="app-container" dir={lang === "ar" ? "rtl" : "ltr"}>
        <div className="gate-screen">
          <h1>{t("consentTitle", lang)}</h1>
          <p>{t("consentBody", lang)}</p>
          {error && <div className="error-banner">{error}</div>}
          <button className="primary-button" disabled={consenting} onClick={handleAcceptConsent}>
            {t("consentAccept", lang)}
          </button>
          <button className="secondary-button" onClick={() => session.setPatientId("")}>
            {t("consentDecline", lang)}
          </button>
        </div>
      </div>
    );
  }

  // --- Main chat ---
  return (
    <div className="app-container" dir={lang === "ar" ? "rtl" : "ltr"}>
      <div className="top-bar">
        <div className="brand">
          Care<span>Flow</span>
        </div>
        <div className="top-bar-actions">
          <button className="icon-button" onClick={() => sendMessage(lang === "ar" ? "أريد التحدث مع شخص" : "I want to talk to a person")}>
            {t("talkToPerson", lang)}
          </button>
          {voiceSupport.tts && (
            <button
              className={`icon-button ${autoSpeak ? "active" : ""}`}
              onClick={toggleAutoSpeak}
              aria-pressed={autoSpeak}
            >
              {t(autoSpeak ? "speakRepliesOn" : "speakRepliesOff", lang)}
            </button>
          )}
          <button className="icon-button" onClick={() => session.setLang(lang === "ar" ? "en" : "ar")}>
            {t("languageToggle", lang)}
          </button>
        </div>
      </div>

      <div className="safety-banner">{t("safetyBanner", lang)}</div>
      {everEscalated && <div className="escalated-banner">{t("escalatedBanner", lang)}</div>}

      <div className="chat-scroll" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i}>
            <div className={`bubble-row ${m.role}`}>
              <div className={`bubble ${m.role}`}>{m.text}</div>
            </div>
            {m.offeredSlots && (
              <div className={`cards-row ${m.role === "patient" ? "" : ""}`} style={{ marginInlineStart: m.role === "assistant" ? 0 : "auto" }}>
                {m.offeredSlots.map((slot) => (
                  <div className="option-card" key={slot.index}>
                    <div>
                      <div className="option-time">{formatTime(slot.start, lang)}</div>
                      <div className="option-meta">
                        {t("with", lang)} {slot.practitioner_id}
                      </div>
                    </div>
                    <button onClick={() => sendMessage(String(slot.index + 1))}>{t("confirmSlot", lang)}</button>
                  </div>
                ))}
              </div>
            )}
            {m.cancellableAppointments && (
              <div className="cards-row">
                {m.cancellableAppointments.map((appt) => (
                  <div className="option-card" key={appt.index}>
                    <div className="option-time">{formatTime(appt.start, lang)}</div>
                    <button onClick={() => sendMessage(String(appt.index + 1))}>{t("confirmCancel", lang)}</button>
                  </div>
                ))}
              </div>
            )}
            {(m.bookingStage === "awaiting_confirmation" || m.cancelStage === "awaiting_confirmation") && (
              <div className="yesno-row">
                <button className="affirmative" onClick={() => sendMessage(t("yes", "en"))}>
                  {t("yes", lang)}
                </button>
                <button onClick={() => sendMessage(t("no", "en"))}>{t("no", lang)}</button>
              </div>
            )}
          </div>
        ))}
        {sending && <div className="typing-indicator">{t("sending", lang)}</div>}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage(draft);
        }}
      >
        {voiceSupport.stt && (
          <button
            type="button"
            className={`mic-button ${listening ? "listening" : ""}`}
            onClick={toggleVoiceInput}
            disabled={sending}
            aria-pressed={listening}
            title={t(listening ? "micListening" : "micStart", lang)}
          >
            🎙
          </button>
        )}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={listening ? t("micListening", lang) : t("inputPlaceholder", lang)}
          disabled={sending || listening}
        />
        <button type="submit" disabled={sending || !draft.trim()}>
          {t("send", lang)}
        </button>
      </form>
    </div>
  );
}
