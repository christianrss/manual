"""Deterministic arithmetic only for the public usage-metering design assessment.

This models idealized event rates and raw data, not infrastructure capacity,
billing correctness, a queue, SLO conformance, or a production recommendation.
Inputs represent counts, bytes, seconds and abstract worker throughput.
"""
SECONDS_PER_DAY = 86_400
BYTES_PER_GIB = 1024 ** 3


def peak_ingest_rate(events_per_day, peak_multiplier):
    """Integer ceiling of mean events/s times a dimensionless peak factor.

    events_per_day >= 0; peak_multiplier >= 1. Both must be plain integers.
    The returned integer is a planning rate, NOT a bounded burst guarantee.
    """
    if (type(events_per_day) is not int or events_per_day < 0
            or type(peak_multiplier) is not int or peak_multiplier < 1):
        raise ValueError("invalid daily count or peak multiplier")
    return -(-(events_per_day * peak_multiplier) // SECONDS_PER_DAY)


def raw_retained_bytes(events_per_day, bytes_per_event, retention_days):
    """Uncompressed logical bytes, no indexes/replication/logs/backups included."""
    if (type(events_per_day) is not int or events_per_day < 0
            or type(bytes_per_event) is not int or bytes_per_event <= 0
            or type(retention_days) is not int or retention_days < 1):
        raise ValueError("invalid event size, count or retention")
    return events_per_day * bytes_per_event * retention_days


def outage_backlog(arrivals_per_second, outage_seconds, prior_events=0):
    """Events pending after no consumers work during a constant-rate outage."""
    if any(type(x) is not int or x < 0 for x in (
            arrivals_per_second, outage_seconds, prior_events)):
        raise ValueError("invalid backlog inputs")
    return prior_events + arrivals_per_second * outage_seconds


def drain_seconds(pending_events, arrivals_per_second, service_per_second):
    """Idealized recovery time with fixed event/s arrivals and consumption.

    A positive surplus is required, even for empty backlog: otherwise the
    returned time would obscure insufficient sustained capacity.
    """
    if (type(pending_events) is not int or pending_events < 0
            or type(arrivals_per_second) is not int or arrivals_per_second < 0
            or type(service_per_second) is not int
            or service_per_second <= arrivals_per_second):
        raise ValueError("a positive recovery margin is required")
    return -(-pending_events // (service_per_second - arrivals_per_second))


def ideal_worker_replicas(peak_rate, measured_worker_rate, target_pct, failed=1):
    """Ceil(peak/(floor(per-worker-rate * target_pct/100))) + failed.

    Workers assumed interchangeable, independently healthy and measured at
    the specified load; shared downstream bottlenecks are deliberately absent.
    This is a hypothetical arithmetic floor, not deployable sizing.
    """
    if (type(peak_rate) is not int or peak_rate < 0
            or type(measured_worker_rate) is not int or measured_worker_rate <= 0
            or type(target_pct) is not int or not 1 <= target_pct <= 100
            or type(failed) is not int or failed < 0):
        raise ValueError("invalid worker planning inputs")
    allowed = measured_worker_rate * target_pct // 100
    if allowed <= 0:
        raise ValueError("zero usable per-worker rate at target utilization")
    return -(-peak_rate // allowed) + failed


if __name__ == "__main__":
    peak = peak_ingest_rate(2_400_000, 40)
    retained = raw_retained_bytes(2_400_000, 2048, 28)
    pending = outage_backlog(1200, 600)
    print({
        "peak_events_per_second_ceil": peak,
        "raw_retained_bytes_28d": retained,
        "raw_retained_gib_28d": round(retained / BYTES_PER_GIB, 2),
        "outage_events": pending,
        "drain_seconds": drain_seconds(pending, 1200, 1800),
        "ideal_worker_replicas": ideal_worker_replicas(peak, 250, 60, 1),
    })
