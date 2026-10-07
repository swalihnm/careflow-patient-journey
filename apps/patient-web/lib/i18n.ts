// Every user-facing string in this app exists in English and Arabic
// (CLAUDE.md engineering rule). The assistant's own replies are already
// bilingual server-side (assistant/language.py detects the patient's
// language per turn); this dictionary covers the static chrome around them.

export type Lang = "en" | "ar";

export const STRINGS = {
  appName: { en: "CareFlow", ar: "كير فلو" },
  safetyBanner: {
    en: "This assistant can't give medical advice, diagnose conditions, or interpret test results.",
    ar: "لا يمكن لهذا المساعد تقديم استشارة طبية أو تشخيص الحالات أو تفسير نتائج الفحوصات.",
  },
  talkToPerson: { en: "Talk to a person", ar: "التحدث مع شخص" },
  languageToggle: { en: "العربية", ar: "English" },
  inputPlaceholder: { en: "Type a message…", ar: "اكتب رسالة…" },
  send: { en: "Send", ar: "إرسال" },
  consentTitle: { en: "Before we start", ar: "قبل أن نبدأ" },
  consentBody: {
    en: "CareFlow uses an AI assistant to help with booking, coverage questions and pre-visit intake. Your messages are logged for quality and safety review. Do you consent to this?",
    ar: "يستخدم كير فلو مساعدا ذكيا للمساعدة في الحجز والأسئلة المتعلقة بالتغطية والفحص المسبق قبل الزيارة. يتم تسجيل رسائلك لمراجعة الجودة والسلامة. هل توافق على ذلك؟",
  },
  consentAccept: { en: "I agree, start chatting", ar: "أوافق، ابدأ المحادثة" },
  consentDecline: { en: "Not now", ar: "ليس الآن" },
  patientIdLabel: { en: "Patient ID (demo)", ar: "رقم المريض (تجريبي)" },
  patientIdPlaceholder: { en: "e.g. test-patient-api", ar: "مثال: test-patient-api" },
  continueButton: { en: "Continue", ar: "متابعة" },
  escalatedBanner: {
    en: "A member of our care team has been alerted and will follow up with you.",
    ar: "تم تنبيه أحد أعضاء فريق الرعاية وسيتواصل معك.",
  },
  confirmSlot: { en: "Book this slot", ar: "احجز هذا الموعد" },
  confirmCancel: { en: "Cancel this appointment", ar: "إلغاء هذا الموعد" },
  yes: { en: "Yes", ar: "نعم" },
  no: { en: "No", ar: "لا" },
  with: { en: "with", ar: "مع" },
  sending: { en: "Sending…", ar: "جارٍ الإرسال…" },
  errorBanner: {
    en: "Something went wrong reaching the assistant. Please try again.",
    ar: "حدث خطأ أثناء الاتصال بالمساعد. يرجى المحاولة مرة أخرى.",
  },
  patientNotFound: {
    en: "We couldn't find that patient ID on file. Double-check it, or ask your clinic to register you first.",
    ar: "لم نتمكن من العثور على رقم المريض هذا. يرجى التحقق منه أو مطالبة عيادتك بتسجيلك أولا.",
  },
  changePatient: { en: "Switch patient", ar: "تبديل المريض" },
  micStart: { en: "Start voice input", ar: "بدء الإدخال الصوتي" },
  micListening: { en: "Listening… tap to stop", ar: "جارٍ الاستماع… اضغط للإيقاف" },
  micError: { en: "Couldn't hear that. Please try typing instead.", ar: "لم نتمكن من سماع ذلك. يرجى المحاولة بالكتابة." },
  speakRepliesOn: { en: "Read replies aloud: on", ar: "قراءة الردود بصوت عال: مفعّل" },
  speakRepliesOff: { en: "Read replies aloud: off", ar: "قراءة الردود بصوت عال: متوقف" },
} satisfies Record<string, Record<Lang, string>>;

export function t(key: keyof typeof STRINGS, lang: Lang): string {
  return STRINGS[key][lang];
}
