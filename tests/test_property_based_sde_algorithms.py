"""Hypothesis-driven oracles for published EN/PT algorithms.

Deliberately checks published solved algorithms, not the unsolved assessment.
"""
import re
from bisect import bisect_left, bisect_right
from itertools import combinations
from pathlib import Path
import sys
import unittest

from hypothesis import given, settings, strategies as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles

FENCE=re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def code(lang,slug):
    namespace={}
    article=load_articles()[lang][slug]
    for match in FENCE.finditer(article["body"]):
        exec(compile(match["code"],f"{lang}/{slug}","exec"),namespace,namespace)
    return namespace

EN_BINARY=code("en","binary-search")
PT_BINARY=code("pt","binary-search")
EN_SIGNED=code("en","algorithm-interview-workshop")
PT_SIGNED=code("pt","algorithm-interview-workshop")

def oracle_shortest(values,target):
    candidates=[]
    for i in range(len(values)):
        total=0
        for j in range(i,len(values)):
            total+=values[j]
            if total>=target:
                candidates.append(j-i+1)
    return min(candidates,default=-1)

class PropertyOracles(unittest.TestCase):
    @settings(max_examples=130,deadline=None,database=None,derandomize=False)
    @given(st.lists(st.integers(-20,20),max_size=28),st.integers(-30,30))
    def test_bounds_both_languages(self,raw,target):
        arr=sorted(raw)
        for ns in (EN_BINARY,PT_BINARY):
            lower=ns.get("lower_bound") or ns.get("limite_inferior")
            upper=ns.get("upper_bound") or ns.get("limite_superior")
            assert lower is not None and upper is not None
            self.assertEqual(lower(arr,target),bisect_left(arr,target))
            self.assertEqual(upper(arr,target),bisect_right(arr,target))

    @settings(max_examples=130,deadline=None,database=None,derandomize=False)
    @given(st.lists(st.integers(-6,6),max_size=14),st.integers(1,20))
    def test_shortest_signed_against_independent_oracle(self,values,target):
        expected=oracle_shortest(values,target)
        self.assertEqual(EN_SIGNED["shortest_at_least"](values,target),expected)
        self.assertEqual(PT_SIGNED["menor_soma_minima"](values,target),expected)

    def test_explicit_minimized_regressions(self):
        self.assertEqual(EN_BINARY["lower_bound"]([2,2],2),0)
        self.assertEqual(PT_SIGNED["menor_soma_minima"]([1,-1,5],5),1)

if __name__=="__main__":
    unittest.main()
