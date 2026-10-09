"""Independent bounded oracles for EN/PT SDE II algorithm examples."""
from __future__ import annotations
from itertools import combinations, product
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles  # noqa: E402

PATTERN = re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def functions(lang, slug):
    article = load_articles()[lang][slug]
    ns = {}
    for match in PATTERN.finditer(article["body"]):
        exec(compile(match.group("code"), f"{lang}/{slug}", "exec"), ns, ns)
    return ns

def compatible(jobs):
    seq = sorted(jobs)
    return all(seq[i-1][1] <= seq[i][0] for i in range(1, len(seq)))

def optimal_count(jobs):
    return max(
        (len(group) for size in range(len(jobs) + 1)
         for group in combinations(jobs, size) if compatible(group)),
        default=0
    )

def quadratic_next_greater(values):
    return [
        next((j for j in range(i+1, len(values)) if values[j] > values[i]), -1)
        for i in range(len(values))
    ]

def brute_histogram(values):
    return max(
        (min(values[i:j]) * (j-i)
         for i in range(len(values)) for j in range(i+1, len(values)+1)),
        default=0
    )

class IndependentAlgorithms(unittest.TestCase):
    def test_greedy_against_all_small_subsets(self):
        candidates = [(a,b) for a in range(4) for b in range(a+1,5)]
        for lang, name in (("en","schedule"),("pt","agendar")):
            fn = functions(lang,"greedy-intervals")[name]
            for size in range(5):
                for jobs in combinations(candidates,size):
                    actual = fn(list(jobs))
                    self.assertTrue(compatible(actual),(lang,jobs,actual))
                    self.assertEqual(len(actual),optimal_count(jobs),(lang,jobs))

    def test_monotonic_against_brute_force(self):
        for lang, nname, hname in (
            ("en","next_greater_index","largest_histogram_rectangle"),
            ("pt","indice_proximo_maior","maior_retangulo")
        ):
            ns = functions(lang,"monotonic-stacks")
            for n in range(6):
                for values in product(range(3),repeat=n):
                    data = list(values)
                    self.assertEqual(ns[nname](data),quadratic_next_greater(data),(lang,data))
                    self.assertEqual(ns[hname](data),brute_histogram(data),(lang,data))

    def test_tree_degenerate_and_nonlocal_bst(self):
        for lang, nname, dname, vname in (
            ("en","Node","diameter_edges","valid_bst"),
            ("pt","No","diametro_arestas","bst_valida")
        ):
            ns = functions(lang,"tree-algorithms")
            node = ns[nname]
            root = node(0)
            cur = root
            for i in range(1,61):
                nxt = node(i)
                if lang == "en":
                    cur.right = nxt
                else:
                    cur.direita = nxt
                cur = nxt
            self.assertEqual(ns[dname](root),60)
            self.assertTrue(ns[vname](root))
            if lang == "en":
                invalid = node(10,None,node(15,node(8)))
            else:
                invalid = node(10,None,node(15,node(8)))
            self.assertFalse(ns[vname](invalid))

if __name__ == "__main__":
    unittest.main()
