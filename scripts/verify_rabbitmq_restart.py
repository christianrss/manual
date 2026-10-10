"""Confirm durable RabbitMQ classic queue message survives SAME CONTAINER restart.

Run only in disposable infrastructure with Docker control. This is not quorum failover.
"""
import os
import subprocess
import time
import uuid

import pika

HOST=os.environ["RABBITMQ_HOST"]
CONTAINER=os.environ["RABBITMQ_CONTAINER_ID"]
QUEUE="manual.restart."+uuid.uuid4().hex
EVENT="restart-"+uuid.uuid4().hex
PARAMS=pika.ConnectionParameters(host=HOST,port=5672,
     connection_attempts=2,retry_delay=1,heartbeat=0,blocked_connection_timeout=15)

def connect_with_deadline(seconds=90):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            return pika.BlockingConnection(PARAMS)
        except (pika.exceptions.AMQPError,OSError):
            time.sleep(1)
    raise TimeoutError("RabbitMQ did not reconnect after restart")

def main():
    publisher=connect_with_deadline(15)
    channel=publisher.channel()
    channel.queue_declare(queue=QUEUE,durable=True,auto_delete=False)
    channel.confirm_delivery()
    channel.basic_publish(exchange="",routing_key=QUEUE,
        body=EVENT.encode("utf-8"),mandatory=True,
        properties=pika.BasicProperties(delivery_mode=2,message_id=EVENT))
    publisher.close()
    # Same Docker container and its existing writable layer are retained.
    subprocess.run(["docker","restart",CONTAINER],check=True,
                   capture_output=True,text=True,timeout=100)
    recovered=connect_with_deadline(90)
    try:
        reader=recovered.channel()
        reader.queue_declare(queue=QUEUE,passive=True)
        method,props,body=reader.basic_get(queue=QUEUE,auto_ack=False)
        if method is None:
            raise AssertionError("confirmed persistent message missing after restart")
        assert body==EVENT.encode("utf-8"),(body,EVENT)
        assert props.message_id==EVENT,(props.message_id,EVENT)
        reader.basic_ack(method.delivery_tag)
        reader.queue_delete(queue=QUEUE)
    finally:
        recovered.close()
    print("RabbitMQ single-node restart preserved confirmed persistent message")

if __name__=="__main__":
    main()
