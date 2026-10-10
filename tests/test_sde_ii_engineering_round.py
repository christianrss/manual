"""Independent EN/PT verification of system and engineering chapter examples."""
from __future__ import annotations
from itertools import combinations_with_replacement
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCES=re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def sample_functions(lang, topic):
    articles=load_articles()
    ns={}
    examples=list(FENCES.finditer(articles[lang][topic]["body"]))
    assert examples, (lang, topic, "no Python examples")
    for x in examples:
        exec(compile(x.group("code"), f"{lang}/{topic}", "exec"), ns, ns)
    return ns

class EngineeringCoreContracts(unittest.TestCase):
    def test_service_dependency_independence(self):
        for language, name in (
            ("en","independent_chain_success"),
            ("pt","sucesso_cadeia_independente"),
        ):
            f=sample_functions(language,"service-boundaries")[name]
            for p in (0.0,0.5,1.0):
                self.assertAlmostEqual(f([p]*3),p**3)
            self.assertAlmostEqual(f([0.99]*3),0.970299)
            with self.assertRaises(ValueError):
                f([-0.01])

    def test_binary_search_regression_oracle(self):
        for language, name in (
            ("en","first_at_least"),("pt","primeiro_pelo_menos"),
        ):
            f=sample_functions(language,"debugging-profiling")[name]
            for n in range(7):
                for values in combinations_with_replacement(range(4),n):
                    for target in range(-1,6):
                        expected=next((i for i,x in enumerate(values) if x>=target),len(values))
                        self.assertEqual(f(values,target),expected)

    def test_canary_sample_and_rate_gates(self):
        for language, name, hold, rejected, eligible in (
            ("en","rollout_decision","hold","rollback","eligible_for_review"),
            ("pt","decisao_rollout","aguardar","reverter","apto_para_revisao"),
        ):
            f=sample_functions(language,"ci-cd-release-engineering")[name]
            self.assertEqual(f(0,0,0,1000),hold)
            self.assertEqual(f(31,1000,5,1000),rejected)
            self.assertEqual(f(1,1000,2,1000),eligible)
            with self.assertRaises(ValueError):
                f(20,10,0,100)

    def test_refactoring_equivalence_and_adapter_boundaries(self):
        for language, old_name, new_name, adapter_name, legacy_name in (
            ("en","old_total","new_total","LegacyAdapter","LegacyQuote"),
            ("pt","total_antigo","total_novo","AdaptadorLegado","CotacaoLegada"),
        ):
            ns=sample_functions(language,"refactoring-design-patterns")
            D=ns["Decimal"]
            old, new=ns[old_name],ns[new_name]
            for cents in range(250):
                value=D(cents)/100
                for policy in ("regular","member"):
                    self.assertEqual(old(value,policy),new(value,policy))
            adapter=ns[adapter_name](ns[legacy_name]())
            self.assertEqual(adapter.total(D("0.00")),D("0.25"))
            with self.assertRaises(ValueError):
                adapter.total(D("-0.01"))

if __name__=="__main__":
    unittest.main()
