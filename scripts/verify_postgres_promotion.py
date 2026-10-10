"""Exercise a disposable PostgreSQL 17 primary and physical standby via Docker.

The script verifies one record has REPLAYED before stopping the primary, then
promotes standby and performs a new write. This is MANUAL promotion after one
process stop; it is NOT automatic failover or a zero-data-loss proof.
"""
import json
import subprocess
import time
import uuid
import psycopg
from failover_metrics import FailoverTiming

TAG=uuid.uuid4().hex[:10]
NETWORK="manual-pgrep-"+TAG
PRIMARY="manual-pg-primary-"+TAG
STANDBY="manual-pg-standby-"+TAG
PVOL="manual-pg-data1-"+TAG
SVOL="manual-pg-data2-"+TAG
IMAGE="postgres:17"
PRIMARY_DSN="postgresql://manual:manual@127.0.0.1:25443/manual"
STANDBY_DSN="postgresql://manual:manual@127.0.0.1:25444/manual"

def docker(*args,timeout=80):
    x=subprocess.run(["docker",*args],capture_output=True,text=True,timeout=timeout)
    if x.returncode:
        raise RuntimeError("docker "+repr(args[:2])+": "+x.stderr[-2500:])
    return x.stdout.strip()

def db_ready(dsn,seconds=70):
    end=time.monotonic()+seconds
    last=None
    while time.monotonic()<end:
        try:
            with psycopg.connect(dsn,connect_timeout=2) as conn:
                conn.execute("SELECT 1")
                return
        except psycopg.Error as exc:
            last=exc
            time.sleep(1)
    raise TimeoutError(f"PostgreSQL not ready: {last}")

def main():
    docker("network","create",NETWORK)
    try:
        for name in (PVOL,SVOL):
            docker("volume","create",name)
        docker("run","-d","--name",PRIMARY,"--hostname","pgprimary",
               "--network",NETWORK,"-p","127.0.0.1:25443:5432",
               "-v",PVOL+":/var/lib/postgresql/data",
               "-e","POSTGRES_USER=manual","-e","POSTGRES_PASSWORD=manual",
               "-e","POSTGRES_DB=manual",IMAGE,
               "-c","wal_level=replica","-c","max_wal_senders=10",timeout=130)
        db_ready(PRIMARY_DSN)
        # The primary permits replication by the example-only superuser.
        docker("exec","-u","postgres",PRIMARY,"sh","-c",
               "printf '\\nhost replication manual 0.0.0.0/0 scram-sha-256\\n' >> /var/lib/postgresql/data/pg_hba.conf")
        docker("exec",PRIMARY,"psql","-U","manual","-d","manual",
               "-tAc","SELECT pg_reload_conf()")
        # Named volume must belong to the PostgreSQL uid before basebackup.
        docker("run","--rm","--user","root",
               "-v",SVOL+":/var/lib/postgresql/data",IMAGE,
               "sh","-c","chown -R postgres:postgres /var/lib/postgresql/data",timeout=100)
        docker("run","--rm","--user","postgres","--network",NETWORK,
               "-v",SVOL+":/var/lib/postgresql/data",
               "-e","PGPASSWORD=manual",IMAGE,
               "pg_basebackup","-h","pgprimary","-U","manual",
               "-D","/var/lib/postgresql/data","-Fp","-Xs","-R",timeout=180)
        docker("run","-d","--name",STANDBY,"--hostname","pgstandby",
               "--network",NETWORK,"-p","127.0.0.1:25444:5432",
               "-v",SVOL+":/var/lib/postgresql/data",IMAGE,
               "-c","hot_standby=on",timeout=140)
        db_ready(STANDBY_DSN)
        with psycopg.connect(STANDBY_DSN) as standby:
            assert standby.execute("SELECT pg_is_in_recovery()").fetchone()[0]
        with psycopg.connect(PRIMARY_DSN) as primary:
            primary.execute("CREATE TABLE manual_probe(id int PRIMARY KEY, payload text NOT NULL)")
            primary.execute("INSERT INTO manual_probe VALUES (1,'replayed-before-stop')")
        # Explicitly wait until standby HAS the row before killing primary.
        replay_started=time.monotonic()
        deadline=time.monotonic()+60
        while True:
            try:
                with psycopg.connect(STANDBY_DSN) as replica:
                    row=replica.execute("SELECT payload FROM manual_probe WHERE id=1").fetchone()
                if row==("replayed-before-stop",):
                    break
            except psycopg.errors.UndefinedTable:
                pass
            if time.monotonic()>deadline:
                raise TimeoutError("standby did not replay the committed marker")
            time.sleep(1)
        # REAL DATA-PLANE PARTITION: old primary keeps running locally.
        # This is NOT a fence; it illustrates why timeout != stopped writer.
        docker("network","disconnect",NETWORK,PRIMARY,timeout=30)
        try:
            running=docker("inspect","--format","{{.State.Running}}",PRIMARY)
            assert running=="true","network disconnect unexpectedly stopped primary"
            # Docker exec communicates through the container runtime, not its
            # database network. A transactional write still succeeds locally.
            probe=docker("exec",PRIMARY,"psql","-U","manual","-d","manual",
                "-tAc","CREATE TEMP TABLE manual_isolated_test(v integer); "
                "INSERT INTO manual_isolated_test VALUES (7); "
                "SELECT SUM(v) FROM manual_isolated_test")
            assert probe.strip().endswith("7"),probe
        finally:
            docker("network","connect","--alias","pgprimary",NETWORK,PRIMARY,timeout=45)
        assert docker("inspect","--format","{{.State.Running}}",PRIMARY)=="true"
        # A previously connected standby should catch up when network heals.
        # The same row used for the earlier RPO marker remains available.
        with psycopg.connect(STANDBY_DSN) as replica:
            assert replica.execute("SELECT payload FROM manual_probe WHERE id=1").fetchone()==("replayed-before-stop",)
        replay_observed_s=round(time.monotonic()-replay_started,3)
        # Suspected unreachability is not fencing. Promotion must refuse
        # while the original instance is still in Docker's running state.
        def require_verified_stop():
            state=docker("inspect","--format","{{.State.Running}}",PRIMARY)
            if state != "false":
                raise RuntimeError("refusing promotion: old primary still running")
        try:
            require_verified_stop()
        except RuntimeError:
            pass
        else:
            raise AssertionError("live primary incorrectly passed the fence gate")
        failover_started=time.monotonic()
        docker("stop","-t","5",PRIMARY,timeout=40)
        require_verified_stop()
        stopped_at=time.monotonic()
        with psycopg.connect(STANDBY_DSN,autocommit=True) as promoted:
            result=promoted.execute("SELECT pg_promote(true, 40)").fetchone()[0]
            if not result:
                raise AssertionError("promotion was not completed")
            assert not promoted.execute("SELECT pg_is_in_recovery()").fetchone()[0]
            promoted_at=time.monotonic()
            promoted.execute("INSERT INTO manual_probe VALUES (2,'new-primary-write')")
            wrote_at=time.monotonic()
            rows=promoted.execute("SELECT id,payload FROM manual_probe ORDER BY id").fetchall()
            assert rows==[(1,"replayed-before-stop"),(2,"new-primary-write")],rows
        timings=FailoverTiming(failover_started,stopped_at,promoted_at,wrote_at).phases()
        timings["marker_replay_observed_s"]=replay_observed_s
        timings["scope"]="one runner; planned stop; manual promotion; not end-to-end RTO or general zero-loss RPO"
        print("POSTGRES_FAILOVER_METRICS "+json.dumps(timings,sort_keys=True))
        print("PASS: primary still writable during network isolation; fenced via controlled stop; standby promoted")
    finally:
        for name in (STANDBY,PRIMARY):
            subprocess.run(["docker","rm","-f",name],capture_output=True,text=True,timeout=45)
        for name in (SVOL,PVOL):
            subprocess.run(["docker","volume","rm","-f",name],capture_output=True,text=True,timeout=45)
        subprocess.run(["docker","network","rm",NETWORK],capture_output=True,text=True,timeout=45)

if __name__=="__main__":
    main()
