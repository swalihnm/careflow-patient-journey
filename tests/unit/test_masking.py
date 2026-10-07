"""PII/PHI masking (SPEC 8.1). Presidio's analyzer is expensive to construct
(loads a spaCy model), so these share one module-scoped instance."""

import pytest

from safety.masking import Masker


@pytest.fixture(scope="module")
def masker() -> Masker:
    return Masker()


def test_masks_person_name(masker):
    result = masker.mask("My name is John Smith and I need an appointment.")
    assert "John Smith" not in result.masked_text
    assert "PERSON" in result.entities_found


def test_masks_email(masker):
    result = masker.mask("Please email me at jane.doe@example.com about this.")
    assert "jane.doe@example.com" not in result.masked_text
    assert "EMAIL_ADDRESS" in result.entities_found


def test_masks_uae_phone_number(masker):
    result = masker.mask("You can reach me at 050-123-4567 anytime.")
    assert "050-123-4567" not in result.masked_text
    assert "UAE_PHONE_NUMBER" in result.entities_found


def test_masks_uae_phone_number_with_country_code(masker):
    result = masker.mask("My number is +971501234567.")
    assert "+971501234567" not in result.masked_text
    assert "UAE_PHONE_NUMBER" in result.entities_found


def test_masks_synthetic_emirates_id(masker):
    result = masker.mask("My ID is 784-1990-1234567-1 for the record.")
    assert "784-1990-1234567-1" not in result.masked_text
    assert "UAE_EMIRATES_ID" in result.entities_found


def test_no_pii_leaves_text_unchanged(masker):
    result = masker.mask("I would like to book an appointment next Tuesday.")
    assert result.masked_text == "I would like to book an appointment next Tuesday."
    assert result.entities_found == []


def test_empty_text_is_a_no_op(masker):
    result = masker.mask("")
    assert result.masked_text == ""
    assert result.entities_found == []
