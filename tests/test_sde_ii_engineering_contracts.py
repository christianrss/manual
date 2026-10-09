"""Cross-language behavioral contracts for SDE II engineering chapters."""
import unittest
from decimal import Decimal
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE=re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang, slug):
    article=load_articles()[lang][slug]
    namespace={}
    examples=list(FENCE.finditer(article["body"]))
    assert examples, (lang,slug,"no python examples")
    for match in examples:
        exec(compile(match["code"],lang+"/"+slug,"exec"),namespace,namespace)
    return namespace

class EngineeringContracts(unittest.TestCase):
    def test_order_composition_and_state(self):
        for lang in ("en","pt"):
            ns=chapter(lang,"object-oriented-design")
            D=ns["Decimal"]
            cls=ns["Order"] if lang=="en" else ns["Pedido"]
            policy=ns["PercentageDiscount"] if lang=="en" else ns["DescontoPercentual"]
            obj=cls(policy(D("0.25")))
            (obj.add if lang=="en" else obj.adicionar)(D("4.00"),2)
            self.assertEqual((obj.submit if lang=="en" else obj.enviar)(),D("6.00"))
            with self.assertRaises(ValueError):
                (obj.submit if lang=="en" else obj.enviar)()
            with self.assertRaises(ValueError):
                policy(D("1.10"))

    def test_dependency_contract_boundaries(self):
        for lang in ("en","pt"):
            ns=chapter(lang,"solid-dependency-inversion")
            D=ns["Decimal"]
            sender=(ns["CollectingSender"] if lang=="en" else ns["RemetenteColetor"])()
            rule=(ns["AlertRule"] if lang=="en" else ns["RegraAlerta"])(sender,D("25"))
            check=rule.check if lang=="en" else rule.verificar
            self.assertFalse(check("ops",D("25")))
            self.assertTrue(check("ops",D("25.01")))
            self.assertEqual(len(sender.messages if lang=="en" else sender.mensagens),1)
            with self.assertRaises(ValueError):
                check("",D("30"))

    def test_billing_properties_and_bounds(self):
        for lang in ("en","pt"):
            ns=chapter(lang,"testing-strategies")
            D=ns["Decimal"]
            f=ns["billed_total"] if lang=="en" else ns["total_cobrado"]
            a=[(D("1.20"),2),(D("0.40"),3)]
            self.assertEqual(f(a,D("0.10")),D("3.96"))
            self.assertEqual(f(list(reversed(a)),D("0.10")),D("3.96"))
            self.assertEqual(f(a+[(D("0"),1)],D("0.10")),D("3.96"))
            with self.assertRaises(ValueError):
                f(a,D("1.01"))

if __name__=="__main__":
    unittest.main()
