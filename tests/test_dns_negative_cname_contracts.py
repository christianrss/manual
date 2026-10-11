"""Independent finite checks for the bilingual negative-cache and CNAME examples.

This oracle derives expected TTL and alias-chain results from generated input
parameters instead of calling the example implementation for expectations.
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

FENCE=re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def published(lang):
    module=types.ModuleType("_negative_dns_"+lang)
    sys.modules[module.__name__]=module
    try:
        body=load_articles()[lang]["dns-authoritative-negative-cname"]["body"]
        blocks=tuple(FENCE.finditer(body))
        if len(blocks)!=2:
            raise AssertionError("expected one negative cache and one CNAME model")
        for index, match in enumerate(blocks,1):
            exec(compile(match["code"], f"{lang}/negative_dns/fence-{index}", "exec"),
                 module.__dict__,module.__dict__)
    finally:
        sys.modules.pop(module.__name__,None)
    return module

class DNSContractTests(unittest.TestCase):
    def test_negative_scope_and_expiry_against_arithmetic_reference(self):
        for lang in ("en","pt"):
            impl=published(lang)
            examined=0
            for mode, kind, lower, upper, soa_ttl, minimum in itertools.product(
                    ("NXDOMAIN","NODATA"),
                    ("A","AAAA","TXT"),
                    ("target.example","TARGET.EXAMPLE."),
                    ("A","AAAA","TXT"),
                    range(5),range(5)):
                negative=impl.NegativeDNSCache()
                actual_ttl=negative.store(lower,mode,kind,soa_ttl,minimum,10)
                duration=min(soa_ttl,minimum)
                self.assertEqual(actual_ttl,duration)
                for now in range(10,17):
                    matching=(mode=="NXDOMAIN" or kind==upper)
                    remaining=duration-(now-10)
                    expected=((mode,remaining) if matching and remaining>0
                              else None)
                    actual=negative.lookup("target.example.",upper,now)
                    self.assertEqual(actual,expected,
                                     (lang,mode,kind,upper,soa_ttl,minimum,now))
                    examined+=1
            self.assertEqual(examined,2*3*2*3*5*5*7)
            self.assertEqual(impl.dns_name("ExAmPlE.test"),"example.test.")
            for invalid in ("",".bad","bad..example","with space.test",
                            "under_score.test","éxample.test"):
                with self.assertRaises(ValueError):
                    impl.dns_name(invalid)
            for kind in ("MX","cname",None,True):
                with self.assertRaises(ValueError):
                    impl.dns_type(kind)
            negative=impl.NegativeDNSCache()
            for invalid in (True,-1,1.5):
                with self.assertRaises(ValueError):
                    negative.store("host.test","NODATA","A",invalid,4,0)
                with self.assertRaises(ValueError):
                    negative.lookup("host.test","A",invalid)
            with self.assertRaises(ValueError):
                negative.store("host.test","SERVFAIL","A",3,3,1)

    def test_explicit_contradictory_event_replacement_and_zero_ttl(self):
        for lang in ("en","pt"):
            cache=published(lang).NegativeDNSCache()
            cache.store("host.test","NODATA","AAAA",50,30,0)
            self.assertEqual(cache.lookup("host.test","AAAA",1),("NODATA",29))
            cache.store("host.test","NXDOMAIN","A",30,20,2)
            self.assertEqual(cache.lookup("host.test","AAAA",3),("NXDOMAIN",19))
            cache.store("host.test","NODATA","A",30,10,4)
            self.assertIsNone(cache.lookup("host.test","AAAA",5))
            self.assertEqual(cache.lookup("host.test","A",5),("NODATA",9))
            cache.store("host.test","NXDOMAIN","A",0,10,5)
            self.assertEqual(cache.lookup("host.test","A",5),("NODATA",9))

    def test_cname_path_ttl_oracle_generated_chains(self):
        for lang in ("en","pt"):
            impl=published(lang)
            count=0
            for hops in range(7):
                for ttl_values in itertools.product((0,1,3),repeat=hops):
                    for terminal_ttl in (0,2,5):
                        terminal="terminal.example"
                        records={terminal:{"A":(("192.0.2.11",),terminal_ttl)}}
                        for index, ttl in enumerate(ttl_values):
                            current=f"alias{index}.example"
                            target=(f"alias{index+1}.example"
                                    if index+1<hops else terminal)
                            records[current]={"CNAME":(target,ttl)}
                        initial=("alias0.example" if hops else terminal)
                        answer=impl.follow_cname(records, initial, max_hops=hops)
                        expected_name=terminal+"."
                        expected_path=tuple(f"alias{i}.example." for i in range(hops))
                        self.assertEqual(
                            answer,
                            impl.AliasAnswer(expected_name,("192.0.2.11",),
                                             min((terminal_ttl,)+ttl_values),
                                             expected_path),
                            (lang,hops,ttl_values,terminal_ttl))
                        if hops:
                            with self.assertRaises(ValueError):
                                impl.follow_cname(records,initial,max_hops=hops-1)
                        count+=1
            self.assertEqual(count,sum(3**n*3 for n in range(7)))

    def test_cname_cycles_missing_rrset_and_invalid_records(self):
        for lang in ("en","pt"):
            fn=published(lang).follow_cname
            with self.assertRaises(ValueError):
                fn({"a.example":{"CNAME":("b.example",5)},
                    "b.example":{"CNAME":("a.example",5)}},"a.example")
            with self.assertRaises(KeyError):
                fn({"a.example":{"CNAME":("missing.example",5)}},"a.example")
            with self.assertRaises(KeyError):
                fn({"a.example":{"A":(("192.0.2.1",),10)}},"a.example","AAAA")
            for data in (
                {"one.example":{"CNAME":("two.example",3),"A":(("192.0.2.1",),4)}},
                {"ONE.example":{"A":(("192.0.2.1",),4)},
                 "one.example.":{"A":(("192.0.2.2",),4)}},
                {"one.example":{"A":((),4)}},
                {"one.example":{"CNAME":("two.example",-1)}},
                {"one.example":{"MX":(("mail.example",),10)}},
                {"one.example":{"A":(("192.0.2.1",),True)}},
            ):
                with self.subTest(lang=lang,data=data):
                    with self.assertRaises(ValueError):
                        fn(data,"one.example")
            for bad in (-1,True,1.5):
                with self.assertRaises(ValueError):
                    fn({},"a.example",max_hops=bad)

if __name__=="__main__":
    unittest.main()
