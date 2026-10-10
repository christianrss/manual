"""Independent finite reference models for bilingual MLFQ and priority donation."""
import itertools
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang):
    mod = types.ModuleType("_priority_scheduling_" + lang)
    sys.modules[mod.__name__] = mod
    try:
        article = load_articles()[lang]["mlfq-priority-inheritance"]["body"]
        for i, match in enumerate(FENCE.finditer(article), 1):
            exec(compile(match["code"], f"{lang}/priority/fence-{i}", "exec"),
                 mod.__dict__, mod.__dict__)
    finally:
        sys.modules.pop(mod.__name__, None)
    return mod

def reference_mlfq(tasks, quanta=(1, 2, 4), boost_interval=0):
    """Tick-wise independently represented queue, using numeric FIFO tickets.

    Selection is by min(priority_level, admission_ticket), with the running
    task tracked separately; no deque of per-level queues is used.
    """
    arrivals = sorted(enumerate(tasks), key=lambda pair: (pair[1].arrival, pair[0]))
    remaining = {t.name: t.work for t in tasks}
    levels, spent, tickets = {}, {}, {}
    ready = set()
    running = None
    now = cursor = ticket_counter = 0
    owners = []
    while any(work > 0 for work in remaining.values()):
        if boost_interval and now and now % boost_interval == 0:
            waiting = sorted(ready, key=lambda name: (levels[name], tickets[name]))
            if running is not None:
                waiting.append(running)
            ready = set(waiting)
            running = None
            for name in waiting:
                levels[name] = spent[name] = 0
                tickets[name] = ticket_counter
                ticket_counter += 1

        while cursor < len(arrivals) and arrivals[cursor][1].arrival <= now:
            name = arrivals[cursor][1].name
            levels[name] = spent[name] = 0
            tickets[name] = ticket_counter
            ticket_counter += 1
            ready.add(name)
            cursor += 1

        if running is not None and any(levels[name] < levels[running] for name in ready):
            tickets[running] = min(
                (tickets[name] for name in ready if levels[name] == levels[running]),
                default=0,
            ) - 1
            ready.add(running)
            running = None

        if running is None and ready:
            running = min(ready, key=lambda name: (levels[name], tickets[name]))
            ready.remove(running)

        if running is None:
            owners.append(None)
            now += 1
            continue

        owners.append(running)
        spent[running] += 1
        remaining[running] -= 1
        if remaining[running] == 0:
            running = None
        elif spent[running] == quanta[levels[running]]:
            levels[running] = min(levels[running] + 1, 2)
            spent[running] = 0
            tickets[running] = ticket_counter
            ticket_counter += 1
            ready.add(running)
            running = None
        now += 1
    return tuple(owners)

def acyclic(edges, names):
    for start in names:
        node, visited = start, set()
        while node in edges:
            if node in visited:
                return False
            visited.add(node)
            node = edges[node]
    return True

def reference_donations(base, edges):
    """For each waiter propagate only its ORIGINAL base rank along owner paths."""
    result = dict(base)
    for waiter, rank in base.items():
        node = waiter
        while node in edges:
            node = edges[node]
            result[node] = max(result[node], rank)
    return result

class PrioritySchedulingContracts(unittest.TestCase):
    def test_exhaustive_mlfq_traces(self):
        possibilities = tuple(itertools.product(range(3), range(1, 4)))
        for lang in ("en", "pt"):
            mod = chapter(lang)
            cases = 0
            for count in range(4):
                for spec in itertools.product(possibilities, repeat=count):
                    jobs = tuple(mod.Task(str(i), arrival, work)
                                 for i, (arrival, work) in enumerate(spec))
                    for quanta in ((1, 2, 4), (2, 3, 4)):
                        for boost in (0, 3, 6):
                            actual = mod.mlfq(jobs, quanta, boost)
                            expected = reference_mlfq(jobs, quanta, boost)
                            self.assertEqual(actual, expected, (lang, spec, quanta, boost))
                            self.assertEqual(sum(owner is not None for owner in actual),
                                             sum(job.work for job in jobs))
                            cases += 1
            self.assertEqual(cases, 4920)

    def test_mlfq_invalid_parameters(self):
        for lang in ("en", "pt"):
            mod = chapter(lang)
            for bad in ([mod.Task("A", 0, 1), mod.Task("A", 1, 1)],
                        [mod.Task("bad ", 0, 1)],
                        [mod.Task("A", True, 1)],
                        [mod.Task("A", 0, 0)],
                        [mod.Task("A", -1, 2)],
                        [mod.Task("A", 0, False)],
                        [object()]):
                with self.subTest(lang=lang, bad=repr(bad)):
                    with self.assertRaises(ValueError):
                        mod.mlfq(bad)
            for bad in ((1, 0, 2), (1, True, 2), (1, 2), [1, 2, 4]):
                with self.assertRaises(ValueError):
                    mod.mlfq([], bad)
            for bad in (True, -1, 1.5):
                with self.assertRaises(ValueError):
                    mod.mlfq([], boost_interval=bad)

    def test_exhaustive_wait_graph_donation(self):
        names = ("A", "B", "C")
        choices = [tuple([None] + [name for name in names if name != waiter])
                   for waiter in names]
        for lang in ("en", "pt"):
            fn = chapter(lang).effective_priorities
            for priorities in itertools.product(range(3), repeat=3):
                base = dict(zip(names, priorities))
                for owners in itertools.product(*choices):
                    edges = {name: owner for name, owner in zip(names, owners)
                             if owner is not None}
                    if not acyclic(edges, names):
                        with self.assertRaises(ValueError):
                            fn(base, edges)
                        continue
                    expected = reference_donations(base, edges)
                    self.assertEqual(fn(base, edges), expected, (lang, base, edges))
            base = {"H": 3, "L": 1, "X": 0, "M": 2}
            self.assertEqual(fn(base, {"H": "L", "L": "X"})["X"], 3)
            self.assertEqual(fn(base, {})["X"], 0)
            for bad_base, bad_edges in (({"A": True}, {}),
                                        ({"A": -1}, {}),
                                        ({"A": 1}, {"A": "A"}),
                                        ({"A": 1}, {"X": "A"}),
                                        ({"A": 1}, {"A": "X"})):
                with self.assertRaises(ValueError):
                    fn(bad_base, bad_edges)

if __name__ == "__main__":
    unittest.main()
