"""SPEC F8 ("Could" priority): voice I/O in apps/patient-web via the
browser's own Web Speech API (lib/speech.ts) -- speech-to-text fills the
composer input, "read replies aloud" speaks each new assistant reply.

Real native SpeechRecognition exists in Playwright's Chromium but won't
produce results headlessly (no mic, no network path to a recognition
service) -- confirmed directly while building this test: the production
code correctly prefers the standard `window.SpeechRecognition` over the
prefixed `window.webkitSpeechRecognition` when both exist, and both exist
natively in Chromium, so a test fake must override *both* properties or the
real (silently inert, headless) one wins. These tests mock the Web Speech
API the same way any hardware-backed browser API gets tested -- there's no
way to feed real audio into a CI browser.
"""

from tests.e2e.conftest import complete_patient_gates

_FAKE_RECOGNITION_INIT = """
class FakeRecognition {
  start() {
    setTimeout(() => {
      if (this.onresult) {
        this.onresult({ results: [[{ transcript: 'what are your clinic hours' }]] });
      }
      if (this.onend) this.onend();
    }, 50);
  }
  stop() {}
}
window.SpeechRecognition = FakeRecognition;
window.webkitSpeechRecognition = FakeRecognition;
"""


def test_mic_button_fills_composer_from_speech_recognition(page, patient_id):
    page.add_init_script(_FAKE_RECOGNITION_INIT)
    complete_patient_gates(page, patient_id)

    mic = page.locator(".mic-button")
    assert mic.count() == 1, "expected a mic button once SpeechRecognition is detected as supported"
    mic.click()

    page.wait_for_function(
        "document.querySelector('.composer input')?.value === 'what are your clinic hours'", timeout=5_000
    )


def test_read_replies_aloud_speaks_each_new_assistant_reply(page, patient_id):
    page.add_init_script("window.__ttsCalls = [];")
    complete_patient_gates(page, patient_id)

    # Patch speechSynthesis.speak to record calls instead of actually
    # speaking -- headless Chromium has no audio output to verify against,
    # so recording what *would* be spoken is the real, checkable signal.
    page.evaluate("""() => {
        window.speechSynthesis.speak = function (utterance) {
            window.__ttsCalls.push({ text: utterance.text, lang: utterance.lang });
        };
    }""")

    page.click("button:has-text('Read replies aloud')")
    page.fill(".composer input", "What are your clinic hours for general practice?")
    page.click("button:has-text('Send')")
    page.wait_for_timeout(2_000)

    tts_calls = page.evaluate("window.__ttsCalls")
    assert len(tts_calls) == 1
    assert tts_calls[0]["lang"] == "en-US"
    assert len(tts_calls[0]["text"]) > 0
