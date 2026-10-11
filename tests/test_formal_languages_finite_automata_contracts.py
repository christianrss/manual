"""Independent checks of the bilingual DFA/epsilon-NFA construction.

The oracle is a direct BFS over (NFA-state, consumed-input-position) pairs;
it deliberately does NOT use epsilon_closure, determinize, or DFA transitions.
Finite tests establish bounded model agreement, not the general induction
theorem stated in the chapters.
"""
from collections import deque
from itertools import product
from pathlib import Path
import random
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

ID = "formal-languages-finite-automata"
FENCE = re.compile(r"(?ms)^~~~python\n(?P<code>.*?)^~~~[ \t]*$")


def direct_accepts(word, start, finals, edges):
    """Independent epsilon-NFA reachability over finite configurations."""
    pending = deque([(start, 0)])
    visited = set()
    while pending:
        state, offset = pending.popleft()
        if (state, offset) in visited:
            continue
        visited.add((state, offset))
        if offset == len(word) and state in finals:
            return True
        for target in edges.get((state, None), ()):
            pending.append((target, offset))
        if offset < len(word):
            for target in edges.get((state, word[offset]), ()):
                pending.append((target, offset + 1))
    return False


def binary_words(max_len):
    for n in range(max_len + 1):
        for seq in product("01", repeat=n):
            yield "".join(seq)


def examples():
    articles = load_articles()
    for lang in ("en", "pt"):
        body = articles[lang][ID]["body"]
        matches = list(FENCE.finditer(body))
        if len(matches) != 1:
            raise AssertionError((lang, "expected one complete code fence"))
        ns = {}
        exec(compile(matches[0].group("code"), f"{lang}/{ID}.py", "exec"), ns, ns)
        yield lang, ns, matches[0].group("code")


class FormalLanguagesAndAutomataContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snippets = list(examples())

    def test_metadata_bilingual_parity_and_prerequisite_order(self):
        articles = load_articles()
        self.assertEqual(load_modules()[ID], "foundations")
        for lang, ns, source in self.snippets:
            self.assertEqual(articles[lang][ID]["meta"]["prerequisites"],
                ["logic-proofs-invariants", "discrete-relations-orders",
                 "graph-traversal"])
            self.assertIn("epsilon_closure", source)
            self.assertIn("determinize", source)
            self.assertEqual(ns["ALPHABET"], ("0", "1"))
        self.assertEqual(self.snippets[0][2], self.snippets[1][2])
        for track in load_tracks()[:2]:
            ids = [item for section in track["sections"]
                   for item in section["articles"]]
            for prereq in articles["en"][ID]["meta"]["prerequisites"]:
                self.assertLess(ids.index(prereq), ids.index(ID))

    def test_example_complete_binary_language_through_length_nine(self):
        for lang, ns, _ in self.snippets:
            for word in binary_words(9):
                with self.subTest(lang=lang, word=word):
                    predicted = ns["accepts_dfa"](word, ns["dfa"])
                    expected = word.endswith("01")
                    self.assertEqual(predicted, expected)
                    self.assertEqual(predicted, direct_accepts(
                        word, 3, {2}, ns["edges"]))

    def test_deterministic_sink_empty_word_and_epsilon_cycle(self):
        for lang, ns, _ in self.snippets:
            make, run = ns["determinize"], ns["accepts_dfa"]
            empty = make({0}, 0, set(), {})
            self.assertEqual(empty[3], (frozenset({0}), frozenset()))
            self.assertEqual(len(empty[2]), 4)
            self.assertFalse(run("", empty))
            self.assertFalse(run("001011", empty))
            self.assertEqual(empty[2][(1, "0")], 1)
            self.assertEqual(empty[2][(1, "1")], 1)
            epsilon = {(0, None): {1}, (1, None): {0},
                       (1, "0"): {2}, (2, "1"): {2}}
            constructed = make({0, 1, 2, 9}, 0, {1, 2}, epsilon)
            self.assertTrue(run("", constructed))
            self.assertTrue(run("0", constructed))
            self.assertTrue(run("011", constructed))
            self.assertFalse(run("1", constructed))
            self.assertFalse(run("00", constructed))
            for word in binary_words(7):
                self.assertEqual(run(word, constructed),
                                 direct_accepts(word, 0, {1, 2}, epsilon))

    def test_seeded_nfas_independent_configuration_graph_oracle(self):
        for lang, ns, _ in self.snippets:
            make, run = ns["determinize"], ns["accepts_dfa"]
            for state_count in (1, 2, 3, 4):
                states = set(range(state_count))
                for seed in range(35):
                    rng = random.Random(state_count * 1_000 + seed)
                    ends = {s for s in states if rng.randrange(3) == 0}
                    edges = {}
                    for start in states:
                        for symbol in (None, "0", "1"):
                            targets = {target for target in states
                                       if rng.randrange(5) == 0}
                            if targets:
                                edges[(start, symbol)] = targets
                    dfa = make(states, 0, ends, edges)
                    initial, finals, transitions, subsets = dfa
                    self.assertEqual(initial, 0)
                    self.assertLessEqual(len(subsets), 2 ** state_count)
                    self.assertEqual(len(transitions), 2 * len(subsets))
                    self.assertEqual(set(range(len(subsets))),
                                     {s for s, _ in transitions})
                    for word in binary_words(6):
                        with self.subTest(lang=lang, count=state_count,
                                          seed=seed, word=word):
                            self.assertEqual(run(word, dfa),
                                             direct_accepts(word, 0, ends, edges))

    def test_invalid_binary_words_and_invalid_graph_edges(self):
        for lang, ns, _ in self.snippets:
            for invalid in ("2", "01a", "0 ", "", None, 10, True):
                # Empty binary word is valid, unlike out-of-alphabet inputs.
                if invalid == "":
                    self.assertIsInstance(ns["accepts_dfa"](invalid, ns["dfa"]), bool)
                    continue
                with self.subTest(lang=lang, word=invalid):
                    with self.assertRaises(ValueError):
                        ns["accepts_dfa"](invalid, ns["dfa"])
            invalid_nfas = [
                ({0}, 1, set(), {}),
                ({0}, 0, {1}, {}),
                (set(), 0, set(), {}),
                ({0}, 0, set(), {(0, "2"): {0}}),
                ({0}, 0, set(), {(1, "0"): {0}}),
                ({0}, 0, set(), {(0, "0"): {1}}),
            ]
            for params in invalid_nfas:
                with self.subTest(lang=lang, nfa=params):
                    with self.assertRaises(ValueError):
                        ns["determinize"](*params)


if __name__ == "__main__":
    unittest.main()
