"""Independent checks for bilingual SDE II lifecycle and interview workshop examples."""
from __future__ import annotations
import re
import sys
import unittest
from itertools import combinations_with_replacement
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles

FENCE=re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang, ident):
    article=load_articles()[lang][ident]
    ns={}
    matches=list(FENCE.finditer(article["body"]))
    assert matches,(lang,ident,"missing examples")
    for match in matches:
        exec(compile(match["code"],f"{lang}/{ident}","exec"),ns,ns)
    return ns

class WorkshopContracts(unittest.TestCase):
    def test_lifecycle_guards(self):
        for lang, name in (("en","advance"),("pt","avancar")):
            f=chapter(lang,"software-project-lifecycle")[name]
            for path in (("requested","running","ready","expired"),
                         ("requested","running","failed")):
                current=path[0]
                for nxt in path[1:]:
                    current=f(current,nxt)
                self.assertEqual(current,path[-1])
            for state, nxt in (("requested","expired"),("ready","failed"),
                               ("failed","requested")):
                with self.assertRaises(ValueError):
                    f(state,nxt)

    def test_rooms_against_sweep_oracle(self):
        for lang, name in (("en","min_rooms"),("pt","minimo_salas")):
            f=chapter(lang,"algorithm-interview-workshop")[name]
            pairs=[(a,b) for a in range(3) for b in range(a+1,5)]
            for size in range(4):
                for data in combinations_with_replacement(pairs,size):
                    expected=max((sum(a<=t<b for a,b in data)
                                  for t,_ in data),default=0)
                    self.assertEqual(f(data),expected,(lang,data))
            with self.assertRaises(ValueError):
                f([(1,1)])

    def test_shortest_signed_subarray_against_naive(self):
        for lang, name in (("en","shortest_at_least"),
                           ("pt","menor_soma_minima")):
            f=chapter(lang,"algorithm-interview-workshop")[name]
            for items in ([5,-10,4,3],[3,-1,4,-2,1],[-2,-2],[],[0,0,0]):
                for goal in range(1,8):
                    lengths=[j-i for i in range(len(items))
                             for j in range(i+1,len(items)+1)
                             if sum(items[i:j])>=goal]
                    self.assertEqual(f(items,goal),min(lengths,default=-1))

    def test_webhook_backoff_and_drain(self):
        for lang, delay, drain in (
            ("en","retry_delay_seconds","drain_seconds"),
            ("pt","atraso_tentativa","segundos_drenagem")):
            ns=chapter(lang,"system-design-interview-workshop")
            self.assertEqual([ns[delay](x,base=3,**({"cap":5} if lang=="en" else {"teto":5}))
                              for x in (1,2,3,1000)],[3,5,5,5])
            self.assertEqual(ns[drain](500,120,520),(60000,3000))
            with self.assertRaises(ValueError):
                ns[drain](500,120,500)

if __name__=="__main__":
    unittest.main()
