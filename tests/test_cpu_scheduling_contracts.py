"""Independent tick-by-tick oracles for bilingual FCFS and Round Robin examples."""
import itertools
import re
import sys
import types
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang):
    module = types.ModuleType("_cpu_scheduling_" + lang)
    sys.modules[module.__name__] = module
    try:
        body = load_articles()[lang]["cpu-scheduling-fcfs-round-robin"]["body"]
        for i, match in enumerate(FENCE.finditer(body), 1):
            exec(compile(match["code"], f"{lang}/scheduling/fence-{i}", "exec"),
                 module.__dict__, module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)
    return module

def reference_round_robin(specs, quantum):
    arrivals = sorted(enumerate(specs), key=lambda pair: (pair[1][1], pair[0]))
    remaining = {name: burst for name, _, burst in specs}
    ready = deque()
    current = None
    used = 0
    cursor = 0
    tick = 0
    timeline = []
    while any(value > 0 for value in remaining.values()):
        # Admission precedes a preempted job being appended at a quantum boundary.
        while cursor < len(arrivals) and arrivals[cursor][1][1] <= tick:
            ready.append(arrivals[cursor][1][0])
            cursor += 1
        if current is not None and used == quantum:
            ready.append(current)
            current = None
            used = 0
        if current is None:
            if ready:
                current = ready.popleft()
            else:
                timeline.append(None)
                tick += 1
                continue
        timeline.append(current)
        remaining[current] -= 1
        used += 1
        tick += 1
        if remaining[current] == 0:
            current = None
            used = 0
    return tuple(timeline)

def reference_fcfs(specs):
    arrivals = sorted(enumerate(specs), key=lambda pair: (pair[1][1], pair[0]))
    timeline = []
    for _, (name, arrival, burst) in arrivals:
        timeline.extend([None] * max(0, arrival - len(timeline)))
        timeline.extend([name] * burst)
    return tuple(timeline)

def expand_trace(trace):
    if not trace:
        return ()
    owners = [None] * max(segment.end for segment in trace)
    for segment in trace:
        assert 0 <= segment.start < segment.end <= len(owners)
        for tick in range(segment.start, segment.end):
            assert owners[tick] is None, "one CPU cannot run multiple jobs"
            owners[tick] = segment.name
    return tuple(owners)

def reference_metrics(specs, owners):
    results = {}
    for name, arrival, burst in specs:
        ticks = [index for index, owner in enumerate(owners) if owner == name]
        assert len(ticks) == burst
        response = ticks[0] - arrival
        turnaround = ticks[-1] + 1 - arrival
        results[name] = (response, turnaround - burst, turnaround)
    return results

class SchedulingContracts(unittest.TestCase):
    def test_all_small_workloads_against_independent_ticks(self):
        inputs = tuple(itertools.product(range(3), (1, 2, 3)))
        for lang in ("en", "pt"):
            mod = chapter(lang)
            for n in range(4):
                for choices in itertools.product(inputs, repeat=n):
                    specs = [(f"J{i}", arrival, burst)
                             for i, (arrival, burst) in enumerate(choices)]
                    jobs = tuple(mod.Job(*triple) for triple in specs)
                    trace = mod.fcfs(jobs)
                    expected = reference_fcfs(specs)
                    self.assertEqual(expand_trace(trace), expected, (lang, specs, "FCFS"))
                    self.assertEqual(mod.scheduling_metrics(jobs, trace),
                                     reference_metrics(specs, expected))
                    for quantum in (1, 2, 3):
                        trace = mod.round_robin(jobs, quantum)
                        expected = reference_round_robin(specs, quantum)
                        self.assertEqual(expand_trace(trace), expected,
                                         (lang, specs, quantum))
                        self.assertEqual(mod.scheduling_metrics(jobs, trace),
                                         reference_metrics(specs, expected))

    def test_quantum_boundary_and_idle_gap(self):
        for lang in ("en", "pt"):
            mod = chapter(lang)
            jobs = (mod.Job("A", 0, 4), mod.Job("B", 2, 1),
                    mod.Job("C", 2, 1))
            self.assertEqual(expand_trace(mod.round_robin(jobs, 2)),
                             ("A", "A", "B", "C", "A", "A"))
            self.assertEqual(expand_trace(mod.round_robin((mod.Job("L", 5, 2),), 1)),
                             (None, None, None, None, None, "L", "L"))

    def test_invalid_inputs_and_quantum(self):
        for lang in ("en", "pt"):
            mod = chapter(lang)
            bad_jobs = (
                [mod.Job("A", 0, 1), mod.Job("A", 1, 1)],
                [mod.Job("A", True, 1)],
                [mod.Job("A", 0, False)],
                [mod.Job("A", -1, 1)],
                [mod.Job("A", 0, 0)],
                [mod.Job(" A ", 0, 1)],
                [object()],
            )
            for jobs in bad_jobs:
                with self.subTest(lang=lang, jobs=str(jobs)):
                    with self.assertRaises(ValueError):
                        mod.fcfs(jobs)
                    with self.assertRaises(ValueError):
                        mod.round_robin(jobs, 2)
            for q in (0, -1, True, 1.5):
                with self.assertRaises(ValueError):
                    mod.round_robin([], q)

if __name__ == "__main__":
    unittest.main()
