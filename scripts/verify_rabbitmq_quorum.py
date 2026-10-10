"""Real three-node RabbitMQ quorum-queue leader failover test.

Intentionally stops an ephemeral leader node. Run ONLY on a disposable Docker host.
Uses separate Docker network/containers and cleans them up even after failure.
"""
import os
import sys
import subprocess
import time
import uuid
import pika

TOKEN=uuid.uuid4().hex[:10]
NETWORK="manual-quorum-"+TOKEN
NODES=[f"manual-mq{i}-{TOKEN}" for i in (1,2,3)]
COOKIE=uuid.uuid4().hex+uuid.uuid4().hex
PORTS=(25673,25674,25675)
QUEUE="manual.quorum."+TOKEN
EVENT="confirmed-"+TOKEN
IMAGE="rabbitmq:4.1"

def docker(*args,timeout=90):
    proc=subprocess.run(["docker",*args],capture_output=True,text=True,timeout=timeout)
    if proc.returncode:
        raise RuntimeError(f"docker {args[:2]} failed: {proc.stderr[-1800:]}")
    return proc.stdout.strip()

def connect(port):
    return pika.BlockingConnection(pika.ConnectionParameters(
        "127.0.0.1",port=port,
        credentials=pika.PlainCredentials("manual","manual"),
        connection_attempts=2,retry_delay=.5,
        socket_timeout=5,stack_timeout=10,blocked_connection_timeout=8,
        heartbeat=0))

def until_ready(node,port,seconds=100):
    # A real AMQP login tests readiness without spawning a new Erlang VM on
    # every poll. Repeated CLI diagnostic invocations can starve small runners.
    deadline=time.monotonic()+seconds
    last=None
    while time.monotonic()<deadline:
        try:
            conn=connect(port)
            conn.close()
            return
        except (pika.exceptions.AMQPError,OSError,TimeoutError) as exc:
            last=exc
            time.sleep(2)
    details=subprocess.run(["docker","logs","--tail","45",node],
                           capture_output=True,text=True,timeout=15)
    raise TimeoutError(f"RabbitMQ AMQP login not ready: {node}: {last}; "
                       f"logs: {details.stderr[-4000:]}")

def receive_on_survivor(port,seconds=90):
    end=time.monotonic()+seconds
    last=None
    while time.monotonic()<end:
        connection=None
        try:
            connection=connect(port)
            channel=connection.channel()
            method,props,body=channel.basic_get(QUEUE,auto_ack=False)
            if method is not None:
                assert body==EVENT.encode(),(body,EVENT)
                assert props.message_id==EVENT,(props.message_id,EVENT)
                channel.basic_ack(method.delivery_tag)
                return
        except (pika.exceptions.AMQPError,OSError,TimeoutError) as exc:
            last=exc
        finally:
            if connection is not None and connection.is_open:
                connection.close()
        time.sleep(2)
    raise TimeoutError(f"confirmed message not recoverable after leader loss: {last}")

def main():
    docker("network","create",NETWORK)
    try:
        for i,node in enumerate(NODES):
            docker("run","-d","--name",node,"--hostname",f"mq{i+1}",
                   "--network",NETWORK,"--memory","768m",
                   "-p",f"127.0.0.1:{PORTS[i]}:5672",
                   "-e",f"RABBITMQ_NODENAME=rabbit@mq{i+1}",
                   "-e",f"RABBITMQ_ERLANG_COOKIE={COOKIE}",
                   "-e","RABBITMQ_DEFAULT_USER=manual",
                   "-e","RABBITMQ_DEFAULT_PASS=manual",
                   "-e","RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=+S 2:2 +A 8",
                   "-e","RABBITMQ_CTL_ERL_ARGS=+S 2:2",
                   IMAGE,timeout=150)
            until_ready(node,PORTS[i])
        for node in NODES[1:]:
            docker("exec",node,"rabbitmqctl","join_cluster","rabbit@mq1",timeout=90)
        status=docker("exec",NODES[0],"rabbitmqctl","cluster_status")
        for name in ("rabbit@mq1","rabbit@mq2","rabbit@mq3"):
            if name not in status:
                raise AssertionError("not a fully joined three-node cluster: "+status[-1400:])
        publisher=connect(PORTS[0])
        try:
            channel=publisher.channel()
            channel.queue_declare(queue=QUEUE,durable=True,
                arguments={"x-queue-type":"quorum","x-quorum-initial-group-size":3})
            channel.confirm_delivery()
            # Confirmed publication completes only when the broker accepts it.
            channel.basic_publish(exchange="",routing_key=QUEUE,
                body=EVENT.encode(),mandatory=True,
                properties=pika.BasicProperties(delivery_mode=2,message_id=EVENT))
        finally:
            publisher.close()
        # Leader placement is client-local by default in this disposable cluster.
        docker("stop","-t","5",NODES[0],timeout=35)
        receive_on_survivor(PORTS[1])
        # A surviving majority should also accept a NEW confirmed publication.
        survivor=connect(PORTS[1])
        try:
            channel=survivor.channel()
            channel.confirm_delivery()
            channel.basic_publish(exchange="",routing_key=QUEUE,
                body=b"after-failover",mandatory=True,
                properties=pika.BasicProperties(delivery_mode=2))
        finally:
            survivor.close()
        # Remove a SECOND member. Only mq2 is alive: 1/3 is not a quorum.
        docker("stop","-t","5",NODES[2],timeout=35)
        health=connect(PORTS[1])
        health.channel()
        health.close()
        # Exercise the actual publisher-confirm code path as a bounded process.
        # An unconfirmed call can hang while quorum is absent; only a positive
        # confirmation would be success, and that must NOT occur here.
        probe=r"""
import sys, pika
port=int(sys.argv[1])
name=sys.argv[2]
conn=pika.BlockingConnection(pika.ConnectionParameters(
    "127.0.0.1",port=port,heartbeat=0,socket_timeout=4,
    stack_timeout=8,blocked_connection_timeout=6,
    credentials=pika.PlainCredentials("manual","manual")))
try:
    ch=conn.channel()
    ch.confirm_delivery()
    ch.basic_publish(exchange="",routing_key=name,body=b"minority-unsafe",
        mandatory=True,properties=pika.BasicProperties(delivery_mode=2))
    print("UNEXPECTED POSITIVE CONFIRM",flush=True)
finally:
    if conn.is_open: conn.close()
"""
        try:
            minority=subprocess.run(
                [sys.executable,"-c",probe,str(PORTS[1]),QUEUE],
                capture_output=True,text=True,timeout=14)
        except subprocess.TimeoutExpired:
            # Time-limited loss of progress is expected without a majority.
            minority=None
        if minority is not None and minority.returncode==0:
            raise AssertionError("quorum queue positively confirmed an unsafe minority write")
        # Restore a second member and demonstrate a fresh confirmed write again.
        docker("start",NODES[2],timeout=40)
        until_ready(NODES[2],PORTS[2])
        deadline=time.monotonic()+75
        last=None
        while time.monotonic()<deadline:
            conn=None
            try:
                conn=connect(PORTS[1])
                ch=conn.channel()
                ch.confirm_delivery()
                ch.basic_publish(exchange="",routing_key=QUEUE,
                    body=b"after-majority-restore",mandatory=True,
                    properties=pika.BasicProperties(delivery_mode=2))
                last=None
                break
            except (pika.exceptions.AMQPError,OSError,TimeoutError) as exc:
                last=exc
                time.sleep(2)
            finally:
                if conn is not None and conn.is_open:
                    conn.close()
        else:
            raise TimeoutError(f"new publish not confirmed after majority restore: {last}")
        print("PASS: 3-node quorum preserved prior event, denied minority positive confirms, and resumed writes after majority restore")
    finally:
        for node in reversed(NODES):
            subprocess.run(["docker","rm","-f",node],capture_output=True,
                           text=True,timeout=40)
        subprocess.run(["docker","network","rm",NETWORK],capture_output=True,
                       text=True,timeout=40)

if __name__=="__main__":
    main()
