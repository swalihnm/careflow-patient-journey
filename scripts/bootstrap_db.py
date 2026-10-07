"""Idempotently creates the trustcore audit-chain tables and the HIE mock's
document table. Run once after `docker compose up` and before seeding/tests."""

from trustcore import db as trustcore_db

from hie import db as hie_db

if __name__ == "__main__":
    trustcore_db.ensure_schema()
    hie_db.ensure_schema()
    print("Schema ready: ops.audit_log, ops.audit_chain_head, ops.hie_documents")
