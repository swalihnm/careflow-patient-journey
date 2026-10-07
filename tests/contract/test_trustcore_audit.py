import trustcore
from trustcore import db as trustcore_db


def test_record_appends_and_links_to_previous_hash():
    r1 = trustcore.record(actor="test", actor_role="system", action="test_action", resource_type="Test")
    r2 = trustcore.record(actor="test", actor_role="system", action="test_action", resource_type="Test")
    assert r2.prev_hash == r1.hash
    assert r2.id > r1.id


def test_verify_chain_ok_after_normal_writes():
    trustcore.record(actor="test", actor_role="system", action="test_action", resource_type="Test")
    result = trustcore.verify_chain()
    assert result.ok
    assert result.first_bad_id is None


def test_verify_chain_detects_tampering():
    r = trustcore.record(actor="test", actor_role="system", action="test_action", resource_type="Test")

    conn = trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE ops.audit_log SET reason = 'tampered' WHERE id = %s", (r.id,))
        conn.commit()

        result = trustcore.verify_chain()
        assert not result.ok
        assert result.first_bad_id == r.id
    finally:
        # Restore the row so the shared chain is valid again for any test
        # that runs after this one (verify_chain checks the whole table).
        with conn.cursor() as cur:
            cur.execute("UPDATE ops.audit_log SET reason = NULL WHERE id = %s", (r.id,))
        conn.commit()
        conn.close()

    assert trustcore.verify_chain().ok
