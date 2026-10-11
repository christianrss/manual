"""Independent, exact-arithmetic contracts for the usage-metering design exercise.

Passing these checks verifies the published math helper and curriculum wiring,
NOT correctness of a reader's system-design response or real infrastructure.
"""
import json
import math
import re
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "examples" / "python"))

from model import load_articles, load_modules, load_tracks
from usage_metering_design_math import (
    BYTES_PER_GIB, SECONDS_PER_DAY,
    peak_ingest_rate, raw_retained_bytes, outage_backlog,
    drain_seconds, ideal_worker_replicas,
)

SCENARIO = json.loads(
    (ROOT / "examples/system-design/usage_metering_scenario.json").read_text(
        encoding="utf-8"
    )
)
ARTICLE_ID = "usage-metering-system-design-assessment"
FENCE = re.compile(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$")


class UsageMeteringArithmeticTests(unittest.TestCase):
    def test_scenario_matches_exact_independent_model(self):
        self.assertEqual(SCENARIO["schema_version"], 1)
        b = SCENARIO["baseline"]
        outage = SCENARIO["outage"]
        expected_peak = math.ceil(Fraction(
            b["events_per_day"] * b["peak_multiplier"], SECONDS_PER_DAY
        ))
        expected_bytes = (b["events_per_day"] * b["bytes_per_event"]
                          * b["raw_retention_days"])
        self.assertEqual(expected_peak, b["expected_peak_event_rate_ceiling"])
        self.assertEqual(
            peak_ingest_rate(b["events_per_day"], b["peak_multiplier"]),
            expected_peak,
        )
        self.assertEqual(expected_bytes, b["expected_raw_retained_bytes"])
        self.assertEqual(
            raw_retained_bytes(
                b["events_per_day"], b["bytes_per_event"], b["raw_retention_days"]
            ), expected_bytes,
        )
        allowed = math.floor(Fraction(
            b["measured_worker_events_per_second"]
            * b["target_worker_utilization_percent"], 100
        ))
        expected_replicas = math.ceil(Fraction(expected_peak, allowed))
        expected_replicas += b["failed_worker_replicas"]
        self.assertEqual(expected_replicas, b["expected_ideal_worker_replicas"])
        self.assertEqual(
            ideal_worker_replicas(
                expected_peak, b["measured_worker_events_per_second"],
                b["target_worker_utilization_percent"],
                b["failed_worker_replicas"],
            ), expected_replicas,
        )
        expected_pending = (
            outage["initial_backlog_events"]
            + outage["steady_arrivals_per_second"] * outage["stopped_processing_seconds"]
        )
        self.assertEqual(expected_pending, outage["expected_backlog_events"])
        self.assertEqual(
            outage_backlog(
                outage["steady_arrivals_per_second"],
                outage["stopped_processing_seconds"],
                outage["initial_backlog_events"],
            ), expected_pending,
        )
        margin = (outage["restored_service_capacity_per_second"]
                  - outage["steady_arrivals_per_second"])
        expected_drain = math.ceil(Fraction(expected_pending, margin))
        self.assertEqual(expected_drain, outage["expected_drain_seconds"])
        self.assertEqual(drain_seconds(
            expected_pending, outage["steady_arrivals_per_second"],
            outage["restored_service_capacity_per_second"]), expected_drain)
        self.assertEqual(BYTES_PER_GIB, 1024**3)

    def test_exact_ceiling_for_large_integers_without_float(self):
        for count in (0, 1, 100, 86399, 86400, 86401, 2_400_000,
                      10**30, 10**1200):
            for multiplier in (1, 2, 7, 40):
                with self.subTest(count_digits=len(str(count)), multiplier=multiplier):
                    expected = math.ceil(Fraction(
                        count * multiplier, SECONDS_PER_DAY
                    ))
                    self.assertEqual(peak_ingest_rate(count, multiplier), expected)
        for n in range(0, 50):
            for factor in (1, 2, 9):
                self.assertEqual(
                    peak_ingest_rate(n, factor),
                    math.ceil(Fraction(n * factor, SECONDS_PER_DAY)),
                )

    def test_outage_and_drain_independent_oracles(self):
        for arrivals in (0, 1, 13, 1200):
            for seconds in (0, 1, 11, 600):
                for initial in (0, 5, 73):
                    pending = arrivals * seconds + initial
                    self.assertEqual(outage_backlog(arrivals, seconds, initial), pending)
                    for surplus in (1, 2, 7, 600):
                        self.assertEqual(
                            drain_seconds(pending, arrivals, arrivals + surplus),
                            math.ceil(Fraction(pending, surplus)),
                        )
                    with self.assertRaises(ValueError):
                        drain_seconds(pending, arrivals, arrivals)
                    with self.assertRaises(ValueError):
                        drain_seconds(pending, arrivals, max(0, arrivals - 1))

    def test_worker_replicas_are_ideal_arithmetic_not_a_benchmark(self):
        for peak in (0, 1, 150, 1112, 10**30):
            for measured in (1, 50, 180, 250):
                for pct in (1, 60, 100):
                    allowed = measured * pct // 100
                    if allowed == 0:
                        with self.assertRaises(ValueError):
                            ideal_worker_replicas(peak, measured, pct, 1)
                    else:
                        self.assertEqual(
                            ideal_worker_replicas(peak, measured, pct, 1),
                            math.ceil(Fraction(peak, allowed)) + 1,
                        )
        self.assertEqual(ideal_worker_replicas(1112, 180, 60, 1), 12)

    def test_boundaries_reject_bool_negative_and_zero_margins(self):
        invalid = [
            (peak_ingest_rate, (-1, 1)),
            (peak_ingest_rate, (0, 0)),
            (peak_ingest_rate, (True, 3)),
            (peak_ingest_rate, (10, False)),
            (peak_ingest_rate, (0.5, 3)),
            (raw_retained_bytes, (0, 0, 2)),
            (raw_retained_bytes, (1, True, 2)),
            (raw_retained_bytes, (1, 1, 0)),
            (raw_retained_bytes, (1, 1, False)),
            (outage_backlog, (-1, 1)),
            (outage_backlog, (2, -1)),
            (outage_backlog, (True, 1)),
            (outage_backlog, (2, 4, True)),
            (drain_seconds, (1, 5, 5)),
            (drain_seconds, (1, 5, 4)),
            (drain_seconds, (0, 5, 0)),
            (drain_seconds, (0, False, 5)),
            (ideal_worker_replicas, (10, 0, 60)),
            (ideal_worker_replicas, (10, 250, 0)),
            (ideal_worker_replicas, (10, 250, 101)),
            (ideal_worker_replicas, (10, True, 50)),
            (ideal_worker_replicas, (10, 100, 0.5)),
            (ideal_worker_replicas, (10, 100, 50, -1)),
            (ideal_worker_replicas, (1, 1, 1)),
        ]
        for fn, args in invalid:
            with self.subTest(function=fn.__name__, args=args):
                with self.assertRaises(ValueError):
                    fn(*args)

    def test_bilingual_examples_and_learning_order(self):
        self.assertEqual(load_modules()[ARTICLE_ID], "interview-practice")
        articles = load_articles()
        snippets = []
        for language in ("en", "pt"):
            chapter = articles[language][ARTICLE_ID]
            self.assertEqual(chapter["meta"]["prerequisites"], [
                "capacity-estimation", "system-design-process",
                "asynchronous-messaging", "database-consistency",
                "data-partitioning-sharding",
            ])
            body = chapter["body"]
            for name in ("usage_metering_scenario.json",
                         "usage_metering_submission_template.md",
                         "usage_metering_design_math"):
                self.assertIn(name, body)
            snippets += FENCE.findall(body)
        self.assertEqual(len(snippets), 2)
        self.assertEqual(snippets[0], snippets[1])
        for track in load_tracks()[:1]:
            ids = [x for section in track["sections"] for x in section["articles"]]
            for required in articles["en"][ARTICLE_ID]["meta"]["prerequisites"]:
                self.assertLess(ids.index(required), ids.index(ARTICLE_ID))
            self.assertLess(ids.index("adaptive-system-design-assessment"),
                            ids.index(ARTICLE_ID))
            self.assertLess(ids.index(ARTICLE_ID), ids.index("evidence-based-interviews"))

    def test_scenario_has_distinct_adversarial_changes_and_scoring_template(self):
        changes = SCENARIO["changes"]
        self.assertEqual(len(changes), 4)
        self.assertEqual(len({change["id"] for change in changes}), 4)
        s = (ROOT / "examples/system-design/usage_metering_submission_template.md"
             ).read_text(encoding="utf-8")
        for n in (10, 15, 20):
            self.assertIn(f"({n} points)", s)
        self.assertIn("Blocking failures", s)
        self.assertIn("human review", s)


if __name__ == "__main__":
    unittest.main()
