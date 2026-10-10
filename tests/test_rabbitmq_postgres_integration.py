"""Real RabbitMQ requeue on lost ack + PostgreSQL transactional inbox."""
import os
import time
import unittest
import uuid

import pika
import psycopg

@unittest.skipUnless(os.getenv("POSTGRES_DSN") and os.getenv("RABBITMQ_HOST"),
                     "PostgreSQL and RabbitMQ hosts required; configured in CI")
class BrokerIntegration(unittest.TestCase):
    def test_unacked_message_is_redelivered_and_deduped(self):
        dsn=os.environ["POSTGRES_DSN"]
        host=os.environ["RABBITMQ_HOST"]
        event="evt-"+uuid.uuid4().hex
        queue="manual.test."+uuid.uuid4().hex
        table="inbox_"+uuid.uuid4().hex
        with psycopg.connect(dsn,autocommit=True) as db:
            db.execute(f'CREATE TABLE "{table}" (event_id text PRIMARY KEY, effects int NOT NULL)')
            self.addCleanup(lambda: self._drop(dsn,table))
        params=pika.ConnectionParameters(host=host,port=5672,
                         heartbeat=0,blocked_connection_timeout=10)
        publisher=pika.BlockingConnection(params)
        ch=publisher.channel()
        ch.queue_declare(queue=queue,durable=True,auto_delete=False)
        self.addCleanup(self._delete_queue,params,queue)
        ch.confirm_delivery()
        assert ch.basic_publish(exchange="",routing_key=queue,
                body=event.encode(),
                properties=pika.BasicProperties(delivery_mode=2,message_id=event),
                mandatory=True)
        publisher.close()

        # First consumer commits its local effect but disappears before ACK.
        first=pika.BlockingConnection(params)
        first_ch=first.channel()
        method,props,payload=first_ch.basic_get(queue=queue,auto_ack=False)
        self.assertIsNotNone(method)
        self.assertEqual(payload,event.encode())
        self.assertTrue(self._consume(dsn,table,event))
        first.close()

        second=pika.BlockingConnection(params)
        second_ch=second.channel()
        try:
            deadline=time.monotonic()+8
            while True:
                method,props,payload=second_ch.basic_get(queue=queue,auto_ack=False)
                if method is not None or time.monotonic()>deadline:
                    break
                time.sleep(.1)
            self.assertIsNotNone(method,"unacknowledged delivery not requeued")
            self.assertEqual(payload,event.encode())
            self.assertTrue(method.redelivered)
            self.assertFalse(self._consume(dsn,table,event))
            second_ch.basic_ack(method.delivery_tag)
        finally:
            second.close()
        with psycopg.connect(dsn) as conn:
            effect=conn.execute(f'SELECT SUM(effects) FROM "{table}"').fetchone()[0]
        self.assertEqual(effect,1)

    @staticmethod
    def _consume(dsn,table,event):
        with psycopg.connect(dsn) as conn:
            inserted=conn.execute(
                f'INSERT INTO "{table}" VALUES (%s,1)'
                " ON CONFLICT(event_id) DO NOTHING RETURNING event_id",
                (event,)).fetchone()
        return bool(inserted)

    @staticmethod
    def _drop(dsn,table):
        with psycopg.connect(dsn,autocommit=True) as conn:
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')

    @staticmethod
    def _delete_queue(params,queue):
        try:
            connection=pika.BlockingConnection(params)
            connection.channel().queue_delete(queue=queue)
            connection.close()
        except pika.exceptions.AMQPError:
            pass

if __name__=="__main__":
    unittest.main()
