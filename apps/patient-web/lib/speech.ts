// SPEC F8 ("Could" priority, the lowest): voice I/O via the browser's own
// Web Speech API -- SpeechRecognition for speech-to-text, speechSynthesis
// for text-to-speech. No dedicated ASR/TTS backend or model in this repo;
// recognition accuracy and which voices/languages are available depend
// entirely on the browser/OS (well supported in Chrome/Edge, which is also
// what tests/e2e/ runs against; Firefox has no SpeechRecognition support at
// all, Safari's is limited). Every entry point here is feature-detected, so
// the chat works identically -- just without a mic/speaker button -- on a
// browser that doesn't support one or both APIs. No official TypeScript DOM
// types ship for SpeechRecognition, hence the minimal interfaces below
// rather than reaching for `any`.

export type Lang = "en" | "ar";

interface SpeechRecognitionResultLike {
  readonly transcript: string;
}
// Indexed access ([0]), not .item(0) -- both exist on the real
// SpeechRecognitionResultList/AlternativeList, but .item() is easy to get
// wrong in a minimal mock and bracket indexing is the simpler, equally
// correct contract to depend on.
type SpeechRecognitionAlternativeList = ArrayLike<SpeechRecognitionResultLike>;
type SpeechRecognitionResultListLike = ArrayLike<SpeechRecognitionAlternativeList>;
interface SpeechRecognitionEventLike {
  readonly results: SpeechRecognitionResultListLike;
}
interface SpeechRecognitionErrorEventLike {
  readonly error: string;
}
interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function isSpeechRecognitionSupported(): boolean {
  return getSpeechRecognitionCtor() !== null;
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

const RECOGNITION_LANG: Record<Lang, string> = { en: "en-US", ar: "ar-AE" };

export interface ListeningHandle {
  stop: () => void;
}

export function startListening(
  lang: Lang,
  onResult: (transcript: string) => void,
  onEnd: () => void,
  onError: (message: string) => void
): ListeningHandle | null {
  const Ctor = getSpeechRecognitionCtor();
  if (!Ctor) return null;

  const recognition = new Ctor();
  recognition.lang = RECOGNITION_LANG[lang];
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => {
    const transcript = event.results[0]?.[0]?.transcript ?? "";
    onResult(transcript);
  };
  recognition.onerror = (event) => onError(event.error);
  recognition.onend = () => onEnd();

  recognition.start();
  return { stop: () => recognition.stop() };
}

export function speak(text: string, lang: Lang): void {
  if (!isSpeechSynthesisSupported()) return;
  window.speechSynthesis.cancel(); // never overlap/queue replies
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = RECOGNITION_LANG[lang];
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking(): void {
  if (isSpeechSynthesisSupported()) window.speechSynthesis.cancel();
}
