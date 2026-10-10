"""Reproduce write skew in PostgreSQL READ COMMITTED, then prevent it under SERIALIZABLE.

Only run against an isolated disposable PostgreSQL schema. All schemas are generated
in the test suite; do not expose schema selection to untrusted clients.
"""
import psycopg

def attempt_off_call(dsn, schema, doctor, isolation="SERIALIZABLE",
                     after_read=None):
    if isolation not in ("SERIALIZABLE", "READ COMMITTED"):
        raise ValueError("unsupported isolation level")
    if doctor not in ("a", "b"):
        raise ValueError("unknown doctor")
    with psycopg.connect(dsn,options=f"-c search_path={schema}") as db:
        db.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
        count=db.execute("SELECT COUNT(*) FROM oncall WHERE active").fetchone()[0]
        if after_read is not None:
            after_read.wait(timeout=15)
        if count<=1:
            return "denied"
        db.execute("UPDATE oncall SET active=false WHERE doctor=%s",(doctor,))
        return "left"

def retry_off_call(dsn, schema, doctor, max_attempts=4):
    if max_attempts<1:
        raise ValueError("positive retry budget required")
    for attempt in range(max_attempts):
        try:
            # Re-run the decision and the write in an entirely fresh transaction.
            return attempt_off_call(dsn,schema,doctor,"SERIALIZABLE")
        except (psycopg.errors.SerializationFailure,psycopg.errors.DeadlockDetected):
            if attempt==max_attempts-1:
                raise
    raise AssertionError("unreachable")
