"""Roundtrip, corruption and semantic contracts for versioned slot bytecode."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))
from model import load_articles,load_modules,load_tracks
from examples.python.lexical_slot_verifier import compile_slots,run_slots,BytecodeError
from examples.python.versioned_bytecode import (
    dump_bytecode,load_bytecode,evaluate_wire,WireFormatError,
    MAGIC,VERSION,MAX_BYTES,
)
from test_mutable_recursion_compiler_contracts import CASES, direct_eval
from examples.python.stateful_function_compiler import parse_stateful

TOPIC="versioned-bytecode-serialization"


def recalc(envelope):
    payload = json.dumps(envelope["payload"],sort_keys=True,
                         separators=(",",":"),ensure_ascii=True).encode("ascii")
    envelope["sha256"]=hashlib.sha256(payload).hexdigest()
    return json.dumps(envelope,sort_keys=True,separators=(",",":")).encode()


class WireBytecodeContracts(unittest.TestCase):
    def test_deterministic_roundtrip_and_multiple_independent_oracles(self):
        for source,typ,expected in CASES:
            with self.subTest(source=source[:55]):
                old=compile_slots(source)
                blob=dump_bytecode(old)
                self.assertEqual(blob,dump_bytecode(compile_slots(source)))
                self.assertLessEqual(len(blob),MAX_BYTES)
                self.assertIn(b'"version":1',blob)
                restored=load_bytecode(blob)
                self.assertEqual(restored,old)
                self.assertEqual(run_slots(restored),expected)
                self.assertEqual(direct_eval(parse_stateful(source)),expected)
                self.assertEqual(evaluate_wire(source),(typ,expected))

    def test_checksums_version_and_type_tags(self):
        source="let f:Fn(Int)->Int=fn(n:Int)->Int=>n+2 in f(3)"
        data=dump_bytecode(compile_slots(source))
        envelope=json.loads(data)
        self.assertEqual(envelope["magic"],MAGIC)
        self.assertEqual(envelope["version"],VERSION)
        self.assertEqual(run_slots(load_bytecode(data)),Fraction(5))
        for field, replacement in (
            ("magic","ANOTHER-VM"),("version",2),("version",True),
            ("sha256","0"*64),("sha256","not-a-hash"),
        ):
            modified=dict(envelope)
            modified[field]=replacement
            with self.subTest(field=field,replacement=replacement):
                with self.assertRaises(WireFormatError):
                    load_bytecode(json.dumps(modified).encode())
        modified=json.loads(data)
        modified["payload"]["result_type"]=["base","Bool"]
        with self.assertRaises(WireFormatError):
            load_bytecode(recalc(modified))
        # Even a recomputed checksum cannot turn invalid stack bytecode into valid code.
        modified=json.loads(data)
        modified["payload"]["code"]["ops"][0]=["ADD",None,0]
        with self.assertRaises(WireFormatError):
            load_bytecode(recalc(modified))

    def test_forged_wrong_address_and_truncated_flow(self):
        source="let x:Int=2 in x+1"
        orig=json.loads(dump_bytecode(compile_slots(source)))
        for mutation in ("out-of-range","negative","bool","missing-return",
                         "bad-immediate","unknown-opcode"):
            doc=json.loads(json.dumps(orig))
            ops=doc["payload"]["code"]["ops"]
            if mutation=="out-of-range":
                for op in ops:
                    if op[0]=="LOAD_SLOT": op[1]=[0,99]
            elif mutation=="negative":
                for op in ops:
                    if op[0]=="LOAD_SLOT": op[1]=[-1,0]
            elif mutation=="bool":
                for op in ops:
                    if op[0]=="LOAD_SLOT": op[1]=[True,0]
            elif mutation=="missing-return":
                ops.pop()
            elif mutation=="bad-immediate":
                for op in ops:
                    if op[0]=="PUSH_INT": op[1]=False
            else:
                ops[0][0]="HOST_EXEC"
            with self.subTest(mutation=mutation):
                with self.assertRaises(WireFormatError):
                    load_bytecode(recalc(doc))

    def test_strict_bounded_json_parser(self):
        blobs=[
            b"",
            b"{",
            b"\xff",
            b"null",
            b"[]",
            b'{"version":1,"version":1}',
            b'{"x":NaN}',
            b'{"x":1.25}',
            b'{"x":'+b'9'*90+b'}',
            b" "* (MAX_BYTES+1),
        ]
        for value in blobs:
            with self.subTest(value=value[:30]):
                with self.assertRaises(WireFormatError):
                    load_bytecode(value)
        for nonbytes in ("{}",bytearray(b"{}"),None,False):
            with self.assertRaises(WireFormatError):
                load_bytecode(nonbytes)

    def test_vm_execution_limits_survive_roundtrip(self):
        looping=("let rec f:Fn(Int)->Int=fn(n:Int)->Int=>"
                 "f(n+1) in f(0)")
        restored=load_bytecode(dump_bytecode(compile_slots(looping)))
        with self.assertRaisesRegex(RuntimeError,"call-frame limit"):
            run_slots(restored,max_frames=8)
        with self.assertRaisesRegex(RuntimeError,"step limit"):
            run_slots(restored,max_steps=12)

    def test_bilingual_examples_and_curriculum(self):
        chapters=load_articles()
        self.assertEqual(load_modules()[TOPIC],"foundations")
        snippets=[]
        for lang in ("en","pt"):
            item=chapters[lang][TOPIC]
            self.assertEqual(item["meta"]["prerequisites"],
                             ["lexical-addresses-bytecode-verification"])
            for marker in ("versioned_bytecode.py","dump_bytecode",
                           "load_bytecode","WireFormatError",
                           "SHA-256","verify_slots"):
                self.assertIn(marker,item["body"])
            blocks=re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",item["body"])
            self.assertEqual(len(blocks),1)
            snippets.append(blocks[0])
        self.assertEqual(snippets[0],snippets[1])
        for track in load_tracks()[:2]:
            ordered=[x for sec in track["sections"] for x in sec["articles"]]
            self.assertLess(ordered.index("lexical-addresses-bytecode-verification"),
                            ordered.index(TOPIC))


if __name__=="__main__":
    unittest.main()
