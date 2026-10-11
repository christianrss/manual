"""Independent finite oracles for published relations/partial-orders chapter.

Property checks enumerate every binary relation on three vertices. Closure is
cross-checked with a path exploration implementation that does not use
Floyd–Warshall. Coverage is bounded; mathematical arguments remain necessary.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from itertools import product

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

CODE = re.compile(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$")


def implementations():
    result = []
    for lang in ("en", "pt"):
        article = load_articles()[lang]["discrete-relations-orders"]
        blocks = CODE.findall(article["body"])
        assert len(blocks) == 1, f"expected one reproducible {lang} code block"
        names = {}
        exec(compile(blocks[0], f"{lang}/discrete-relations-orders", "exec"), names)
        result.append((lang, names))
    return result


def independent_reachability(n, edges):
    # Reachability oracle: repeated frontier exploration from each starting node.
    answer = set()
    for start in range(n):
        reached = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for a, b in edges:
                if a == current and b not in reached:
                    reached.add(b)
                    frontier.append(b)
        answer.update((start, target) for target in reached)
    return answer


class RelationsOrdersContracts(unittest.TestCase):
    def test_registered_and_prerequisite_order(self):
        self.assertEqual(load_modules()["discrete-relations-orders"], "foundations")
        for track in load_tracks()[:2]:
            core = [ident for sec in track["sections"] for ident in sec["articles"]]
            self.assertLess(core.index("discrete-counting-probability"),
                            core.index("discrete-relations-orders"))
            self.assertLess(core.index("discrete-relations-orders"),
                            core.index("complexity-analysis"))

    def test_all_small_binary_relations_and_graph_paths(self):
        for lang, namespace in implementations():
            flags = namespace["relation_properties"]
            closure = namespace["reflexive_transitive_closure"]
            n = 3
            universe = list(product(range(n), repeat=2))
            for mask in range(1 << (n * n)):
                edges = {pair for bit, pair in enumerate(universe) if mask & (1 << bit)}
                with self.subTest(lang=lang, mask=mask):
                    props = flags(n, edges)
                    is_refl = all((a, a) in edges for a in range(n))
                    is_sym = all((b, a) in edges for a, b in edges)
                    is_antisym = not any(a != b and (b, a) in edges for a, b in edges)
                    is_trans = not any(
                        (a, d) not in edges
                        for a, b in edges for c, d in edges if b == c
                    )
                    self.assertEqual(props["reflexive"], is_refl)
                    self.assertEqual(props["symmetric"], is_sym)
                    self.assertEqual(props["antisymmetric"], is_antisym)
                    self.assertEqual(props["transitive"], is_trans)
                    self.assertEqual(props["equivalence"], is_refl and is_sym and is_trans)
                    self.assertEqual(props["partial_order"], is_refl and is_antisym and is_trans)
                    self.assertEqual(closure(n, edges), independent_reachability(n, edges))

    def test_partition_classes_are_independent_of_labels(self):
        for lang, namespace in implementations():
            fn = namespace["equivalence_classes"]
            for n in range(5):
                for labels in product(range(n), repeat=n):
                    pairs = {(i, j) for i in range(n) for j in range(n)
                             if labels[i] == labels[j]}
                    expected = tuple(
                        tuple(i for i in range(n) if labels[i] == label)
                        for label in sorted(set(labels), key=lambda value: labels.index(value))
                    )
                    with self.subTest(lang=lang, labels=labels):
                        self.assertEqual(fn(n, pairs), expected)
                self.assertEqual(fn(n, {(i, i) for i in range(n)}),
                                 tuple((i,) for i in range(n)))

    def test_reject_invalid_relations_and_nonsensical_classification(self):
        for lang, namespace in implementations():
            normalize = namespace["normalized_relation"]
            classify = namespace["equivalence_classes"]
            with self.subTest(lang=lang):
                for n, pairs in [(-1, []), (True, []), (2.1, []),
                                 (2, [(0, True)]), (2, [(0, 2)]),
                                 (2, [[0, 1]]), (2, [(0,)])]:
                    with self.assertRaises(ValueError):
                        normalize(n, pairs)
                with self.assertRaises(ValueError):
                    classify(3, {(0, 1)})
                self.assertEqual(classify(0, []), ())
                self.assertEqual(namespace["reflexive_transitive_closure"](0, []), set())


if __name__ == "__main__":
    unittest.main()
