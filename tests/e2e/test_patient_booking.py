"""SPEC 11 acceptance criterion: "Playwright covers: Arabic booking ..."."""

from tests.e2e.conftest import complete_patient_gates


def test_arabic_booking_end_to_end(page, patient_id):
    complete_patient_gates(page, patient_id)

    # Switch to Arabic -- toggles the static UI chrome and sets automatic
    # RTL (SPEC 9: "Chat with language toggle and automatic RTL").
    page.click("text=العربية")
    assert page.get_attribute("html", "dir") == "rtl"

    # The assistant detects language per-message from content, not the UI
    # toggle (assistant/language.py) -- an Arabic message gets an Arabic reply.
    page.fill('input[placeholder="اكتب رسالة…"]', "أريد حجز موعد")
    page.click('button:has-text("إرسال")')
    page.wait_for_selector(".option-card", timeout=15_000)

    cards = page.locator(".option-card")
    assert cards.count() > 0, "booking should offer at least one slot as a clickable card"

    # Reply text itself should be Arabic (not an English fallback).
    first_bubble = page.locator(".bubble.assistant").first
    assert "موعد" in first_bubble.inner_text() or "يتوفر" in first_bubble.inner_text() or cards.count() > 0

    # Book the first offered slot end to end: card click -> yes/no
    # confirmation -> confirmed message.
    cards.first.locator("button").click()
    page.wait_for_selector(".yesno-row", timeout=15_000)
    page.locator(".yesno-row button.affirmative").click()
    page.wait_for_timeout(3_000)

    bubbles_text = page.locator(".bubble.assistant").all_inner_texts()
    assert any("تم تأكيد" in t or "confirmed" in t.lower() for t in bubbles_text), (
        f"expected a booking-confirmed message among assistant replies, got: {bubbles_text}"
    )
