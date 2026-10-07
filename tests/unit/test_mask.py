from specmcp.mask import apply_mask


def test_top_level_field_redacted():
    resource = {"resourceType": "Patient", "identifier": [{"value": "123"}], "name": [{"family": "Doe"}]}
    masked = apply_mask(resource, ["identifier"])
    assert masked["identifier"] == "***MASKED***"
    assert masked["name"] == [{"family": "Doe"}]  # untouched


def test_original_resource_not_mutated():
    resource = {"identifier": [{"value": "123"}]}
    apply_mask(resource, ["identifier"])
    assert resource["identifier"] == [{"value": "123"}]


def test_missing_field_is_a_no_op():
    resource = {"resourceType": "Patient"}
    masked = apply_mask(resource, ["telecom"])
    assert masked == {"resourceType": "Patient"}


def test_multiple_fields_redacted():
    resource = {"name": [{"family": "Doe"}], "telecom": [{"value": "123"}], "identifier": [{"value": "x"}]}
    masked = apply_mask(resource, ["name", "telecom", "identifier"])
    assert masked["name"] == "***MASKED***"
    assert masked["telecom"] == "***MASKED***"
    assert masked["identifier"] == "***MASKED***"
