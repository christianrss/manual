"""Finite external oracles for published EN/PT architecture teaching models.

The reference direct-mapped cache test uses the last prior access in a congruence
class rather than the article implementation's tag table. All models are small
and exclude hardware timing, concurrency, coherence and RISC-V conformance.
"""
import itertools
import re
import sys
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles

FENCE=re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def sample(lang):
    name=f"_architecture_{lang}"
    mod=types.ModuleType(name)
    sys.modules[name]=mod
    try:
        body=load_articles()[lang]["machine-representation-isa-cache"]["body"]
        for i,match in enumerate(FENCE.finditer(body),1):
            exec(compile(match.group("code"),f"{name}/block-{i}","exec"),mod.__dict__,mod.__dict__)
    finally:
        sys.modules.pop(name,None)
    return mod

def last_owner_reference(addresses, bytes_per_line, slots):
    # Independent oracle: look backward through all previous accesses to
    # discover which block was last used in the current congruence class.
    answers=[]
    for i,address in enumerate(addresses):
        block=address//bytes_per_line
        owner=None
        for earlier in reversed(addresses[:i]):
            earlier_block=earlier//bytes_per_line
            if earlier_block%slots==block%slots:
                owner=earlier_block
                break
        answers.append(owner==block)
    return answers

class ArchitectureContracts(unittest.TestCase):
    def test_full_8bit_signed_domain_and_all_additions(self):
        for lang in ("en","pt"):
            m=sample(lang)
            signed=m.signed8 if lang=="en" else m.interpretar_assinado8
            add=m.add8 if lang=="en" else m.somar8
            for raw in range(256):
                expected=raw if raw<128 else raw-256
                self.assertEqual(signed(raw),expected,(lang,raw))
            for left in range(256):
                for right in range(256):
                    self.assertEqual(add(left,right),(left+right)%256,(lang,left,right))
            for invalid in (-1,256,True,2.0):
                with self.assertRaises(ValueError):signed(invalid)
                with self.assertRaises(ValueError):add(invalid,1)

    def test_direct_map_last_owner_oracle(self):
        for lang in ("en","pt"):
            m=sample(lang)
            Cache=m.DirectMappedCache if lang=="en" else m.CacheDireta
            for line_size,slots in ((1,1),(2,2),(4,2),(2,3)):
                # Exhaustively inspect every trace of length <= 4 over 5 addresses.
                for size in range(5):
                    for trace in itertools.product(range(5),repeat=size):
                        cache=Cache(line_size,slots)
                        actual=[cache.access(a) if lang=="en" else cache.acessar(a) for a in trace]
                        expected=last_owner_reference(trace,line_size,slots)
                        self.assertEqual(actual,expected,(lang,line_size,slots,trace))
                        h=cache.hits if lang=="en" else cache.acertos
                        miss=cache.misses if lang=="en" else cache.faltas
                        self.assertEqual((h,miss),(sum(expected),len(trace)-sum(expected)))
            cache=Cache(4,2)
            for bad in (-1,True,1.0):
                with self.assertRaises(ValueError):
                    (cache.access if lang=="en" else cache.acessar)(bad)

    def test_toy_machine_execution_and_failure_boundaries(self):
        for lang in ("en","pt"):
            m=sample(lang)
            Machine=m.TinyMachine if lang=="en" else m.MaquinaDidatica
            execute="run" if lang=="en" else "executar"
            for a,b in itertools.product((0,1,127,128,250,255),repeat=2):
                vm=Machine([a,b,0])
                getattr(vm,execute)([("LD",0,0),("LD",1,1),("ADD",2,0,1),("ST",2,2)])
                self.assertEqual(vm.memory[2] if lang=="en" else vm.memoria[2],(a+b)%256)
                self.assertEqual(vm.pc,4)
            vm=Machine([0,1])
            with self.assertRaises(ValueError):
                getattr(vm,execute)([("LD",0,99)])
            self.assertEqual(vm.pc,0)
            with self.assertRaises(ValueError):
                getattr(vm,execute)([("WHAT",)])
            self.assertEqual(vm.pc,0)

if __name__=="__main__":
    unittest.main()
