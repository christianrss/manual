"""Independent, finite tests of published EN/PT Builder, Facade, Observer behavior."""
import re
import sys
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles
PYTHON_FENCE=re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang):
    m=types.ModuleType(f"_patterns_{lang}")
    sys.modules[m.__name__]=m
    try:
        for i,match in enumerate(PYTHON_FENCE.finditer(load_articles()[lang]["design-pattern-families"]["body"]),1):
            exec(compile(match["code"],f"{lang}/design-pattern-families/{i}","exec"),m.__dict__,m.__dict__)
    finally:
        sys.modules.pop(m.__name__,None)
    return m

class PatternContracts(unittest.TestCase):
    def test_builder_rejects_invalid_steps_without_mutation(self):
        for lang in ("en","pt"):
            m=chapter(lang)
            builder=(m.ReportBuilder if lang=="en" else m.ConstrutorRelatorio)("R")
            add=builder.add if lang=="en" else builder.adicionar
            build=builder.build if lang=="en" else builder.construir
            with self.assertRaises(ValueError):build()
            add("A","a")
            initial=build()
            for heading,body in (("A","other"),(" B","b"),("", "empty"),("C"," ")):
                with self.subTest(lang=lang,heading=heading),self.assertRaises(ValueError):
                    add(heading,body)
            self.assertEqual(len((build().sections if lang=="en" else build().secoes)),1)
            add("B","b")
            self.assertEqual(len((initial.sections if lang=="en" else initial.secoes)),1)
            self.assertEqual(len((build().sections if lang=="en" else build().secoes)),2)

    def test_facade_failure_contracts(self):
        for lang in ("en","pt"):
            m=chapter(lang)
            F=m.ProductView if lang=="en" else m.VisaoProduto
            C=m.Catalog if lang=="en" else m.Catalogo
            S=m.StockBook if lang=="en" else m.EstoqueAtual
            name="summary" if lang=="en" else "resumo"
            for n in (None,-1,True,1.5):
                with self.subTest(lang=lang,stock=n),self.assertRaises(ValueError):
                    getattr(F(C({"A":"Ok"}),S({"A":n})),name)("A")
            with self.assertRaises(KeyError):
                getattr(F(C({}),S({"A":4})),name)("A")
            with self.assertRaises(ValueError):
                getattr(F(C({}),S({})),name)("")

    def test_observer_registration_snapshot_and_fail_fast(self):
        for lang in ("en","pt"):
            m=chapter(lang)
            e=m.EventSource() if lang=="en" else m.FonteEventos()
            add=e.subscribe if lang=="en" else e.inscrever
            send=e.publish if lang=="en" else e.publicar
            seen=[]
            def third(x):seen.append(("third",x))
            def first(x):
                seen.append(("first",x))
                if x==1:add(third)
            def second(x):seen.append(("second",x))
            add(first);add(second)
            with self.assertRaises(ValueError):add(first)
            send(1)
            self.assertEqual(seen,[("first",1),("second",1)])
            send(2)
            self.assertEqual(seen[-3:],[("first",2),("second",2),("third",2)])
            f=m.EventSource() if lang=="en" else m.FonteEventos()
            ad=f.subscribe if lang=="en" else f.inscrever
            publish=f.publish if lang=="en" else f.publicar
            calls=[]
            def failing(x):
                calls.append("failing")
                raise RuntimeError("stop")
            ad(failing);ad(lambda x:calls.append("later"))
            with self.assertRaises(RuntimeError):publish(0)
            self.assertEqual(calls,["failing"])

if __name__=="__main__":unittest.main()
