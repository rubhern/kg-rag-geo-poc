import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer


def utc_now_iso() -> str:
    # ISO-8601 UTC like 2026-01-24T09:12:34Z
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_post(dataset: str) -> dict:
    """
    This is a synthetic 'source' event.
    Keep it domain-ish, not a platform envelope.
    """
    source_event_id = str(uuid.uuid4())

    # Example content (keep it boring and predictable)
    texts = [
        "Small traffic incident reported near the city center.",
        "Roadworks causing slow traffic on the main avenue.",
        "Minor incident resolved, traffic back to normal.",
        "Heavy congestion reported near the roundabout.",
    ]

    return {
        "dataset": dataset,                 # helpful for consumers and debugging
        "source_event_id": source_event_id, # stable ID from the source side
        "event_time": utc_now_iso(),        # when it happened at the source (best effort)
        "text": random.choice(texts),
        "author": "simulator",
        "location": {"lat": 41.6523, "lon": -4.7245},  # sample coords (Valladolid-ish)
        "severity": random.choice(["low", "medium", "high"]),
    }

def delivery_report(err, msg) -> None:
    # Called once for each produced message to indicate delivery result.
    if err is not None:
        print(json.dumps({
            "msg": "delivery failed",
            "error": str(err),
            "topic": msg.topic(),
        }))
    else:
        print(json.dumps({
            "msg": "delivered",
            "topic": msg.topic(),
            "partition": msg.partition(),
            "offset": msg.offset(),
        }))


def main() -> None:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC_SOURCE", "source.posts.v1")
    dataset = os.getenv("DATASET", "posts")

    # Sending rate controls
    posts_per_sec = float(os.getenv("POSTS_PER_SEC", "5"))
    total = int(os.getenv("POSTS_TOTAL", "0"))  # 0 = infinite

    # Kafka producer tuning (keep simple for POC)
    producer = Producer({
        "bootstrap.servers": bootstrap,
        "acks": "1",
        "retries": 5,
        "linger.ms": 50,
        "compression.type": "snappy",  # optional, nice for higher throughput
        # "enable.idempotence": True,  # optional; keep off unless you want stronger guarantees
    })

    sent = 0
    try:
        while True:
            post = build_post(dataset=dataset)
            key = post["source_event_id"]

            value_bytes = json.dumps(post).encode("utf-8")

            # Backpressure: if local queue is full, poll and retry
            while True:
                try:
                    producer.produce(
                        topic=topic,
                        key=key.encode("utf-8"),
                        value=value_bytes,
                        on_delivery=delivery_report,
                    )
                    break
                except BufferError:
                    producer.poll(0.1)

            # Serve delivery callbacks (non-blocking)
            producer.poll(0)

            sent += 1
            if 0 < total <= sent:
                break

            time.sleep(max(0.0, 1.0 / posts_per_sec))

            # Ensure all messages are delivered before exiting
        producer.flush(10)
        print(json.dumps({"msg": "producer done", "topic": topic, "sent": sent}))
    finally:
        # flush again just in case (safe)
        producer.flush(5)


if __name__ == "__main__":
    main()
