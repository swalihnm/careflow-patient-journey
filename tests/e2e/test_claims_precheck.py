"""SPEC section 10 stretch module: drives apps/care-web's /claims page
against the real FastAPI backend (POST /v1/claims/precheck, POST/GET
/v1/claims/decisions) and the real RAG-backed coverage check -- nothing
mocked, same convention as the rest of this directory.
"""

from tests.e2e.conftest import CARE_WEB_URL, set_care_web_role


def test_claims_page_forbidden_for_non_admin_role(page):
    page.goto(f"{CARE_WEB_URL}/claims")
    set_care_web_role(page, "clinician")
    assert "can't view this page" in page.locator("main").inner_text()


def test_admin_can_run_precheck_and_record_a_decision(page):
    page.goto(f"{CARE_WEB_URL}/claims")
    set_care_web_role(page, "admin")

    page.get_by_label("Service type").select_option("cosmetic_procedure")
    page.fill("textarea", "Consultation for an elective cosmetic procedure requested by the patient.")
    page.click("button:has-text('Run pre-check')")

    # Cold-start: rag.store's embedding model loads lazily on first query,
    # which has been measured to take several real seconds -- see
    # PROGRESS.md's claims-module section. A short fixed sleep isn't
    # reliable here, so wait on the actual state change instead.
    page.wait_for_function("document.querySelector('button')?.textContent !== 'Running...'", timeout=30_000)
    page.wait_for_selector("h2:has-text('Result:')", timeout=10_000)

    result_card = page.locator(".card", has=page.locator("h2:has-text('Result:')"))
    assert "cosmetic_excluded" in result_card.inner_text()
    assert "insurance_plans" in result_card.inner_text()  # the RAG citation, not a hardcoded string

    result_card.locator("button:has-text('Dismiss')").click()
    page.wait_for_timeout(1_000)

    decisions_card = page.locator(".card", has=page.locator("h2:has-text('Recent decisions')"))
    assert "cosmetic_excluded" in decisions_card.inner_text()
    assert "dismiss" in decisions_card.inner_text()
