"""Independent numerical and finite-event oracles for PT/EN TCP RTO lessons.

The reference computes RTT smoothing with Decimal rather than the article's
binary floating-point state. The congestion reference derives the window
from explicit round events and FlightSize, using an independent state machine.
No live network traffic or complete TCP congestion control is tested.
"""
import itertools
import math
import re
import sys
import types
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles

FENCE=re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang):
    mod=types.ModuleType("_rto_tcp_"+lang)
    sys.modules[mod.__name__]=mod
    try:
        body=load_articles()[lang]["tcp-rto-retransmission-congestion"]["body"]
        blocks=tuple(FENCE.finditer(body))
        if len(blocks)!=2:
            raise AssertionError("expected two Python examples")
        for i,block in enumerate(blocks,1):
            exec(compile(block["code"],f"{lang}/tcp-rto/fence-{i}","exec"),
                 mod.__dict__,mod.__dict__)
    finally:
        sys.modules.pop(mod.__name__,None)
    return mod

class DecimalRtoOracle:
    """Independent Decimal arithmetic and explicit event history."""
    def __init__(self):
        self.samples=[]
        self.backoffs=0
        self.rto=Decimal("1")
        self.srtt=None
        self.rttvar=None

    def observe(self,rtt,ambiguous=False):
        if ambiguous:
            return
        self.samples.append(Decimal(str(rtt)))
        r=self.samples[-1]
        if self.srtt is None:
            self.srtt=r
            self.rttvar=r/Decimal(2)
        else:
            old=self.srtt
            self.rttvar=(Decimal(3)*self.rttvar+abs(old-r))/Decimal(4)
            self.srtt=(Decimal(7)*old+r)/Decimal(8)
        candidate=self.srtt+max(Decimal("0.01"),Decimal(4)*self.rttvar)
        self.rto=min(Decimal(60),max(Decimal(1),candidate))

    def timeout(self):
        self.backoffs+=1
        self.rto=min(Decimal(60),Decimal(2)*self.rto)

class TCPRtoContracts(unittest.TestCase):
    def test_timer_all_short_event_histories_against_decimal(self):
        events=(("sample",0.2),("sample",0.4),("sample",0.6),
                ("ambiguous",0.8),("timeout",None))
        for lang in ("en","pt"):
            cls=chapter(lang).RtoEstimator
            examined=0
            with localcontext() as context:
                context.prec=40
                for length in range(6):
                    for trace in itertools.product(events,repeat=length):
                        clock=cls()
                        oracle=DecimalRtoOracle()
                        for action,value in trace:
                            if action=="timeout":
                                clock.timeout()
                                oracle.timeout()
                            elif action=="sample":
                                clock.observe(value)
                                oracle.observe(value)
                            else:
                                before=(clock.srtt,clock.rttvar,clock.rto)
                                clock.observe(value,retransmitted=True)
                                oracle.observe(value,ambiguous=True)
                                self.assertEqual((clock.srtt,clock.rttvar,clock.rto),before)
                            self.assertAlmostEqual(clock.rto,float(oracle.rto),places=9)
                            self.assertTrue(1<=clock.rto<=60)
                            if oracle.srtt is None:
                                self.assertIsNone(clock.srtt)
                                self.assertIsNone(clock.rttvar)
                            else:
                                self.assertAlmostEqual(clock.srtt,float(oracle.srtt),places=9)
                                self.assertAlmostEqual(clock.rttvar,float(oracle.rttvar),places=9)
                        examined+=1
            self.assertEqual(examined,sum(5**n for n in range(6)))

    def test_rto_rejected_inputs_do_not_mutate(self):
        for lang in ("en","pt"):
            mod=chapter(lang)
            for value in (0,-1,True,False,float("nan"),float("inf"),"0.1"):
                with self.assertRaises(ValueError):
                    mod.RtoEstimator(value)
            timer=mod.RtoEstimator()
            for sample,flag in ((0,False),(-1,False),(float("nan"),False),
                                (float("inf"),False),(True,False),
                                ("0.5",False),(0.5,1)):
                before=(timer.srtt,timer.rttvar,timer.rto)
                with self.assertRaises(ValueError):
                    timer.observe(sample,flag)
                self.assertEqual((timer.srtt,timer.rttvar,timer.rto),before)
            for _ in range(10):
                timer.timeout()
            self.assertEqual(timer.rto,60.0)

class CongestionRoundContracts(unittest.TestCase):
    def test_independent_round_state_transitions(self):
        events=(("success",0),("success",0),("timeout",0),
                ("timeout",3),("timeout",9),("timeout",15))
        for lang in ("en","pt"):
            cls=chapter(lang).RoundCongestionSketch
            examined=0
            for initial in (2,4,8):
                for length in range(5):
                    for trace in itertools.product(events,repeat=length):
                        impl=cls(initial)
                        window=1
                        threshold=initial
                        for event,value in trace:
                            if event=="success":
                                if window<threshold:
                                    window=min(threshold,2*window)
                                else:
                                    window=window+1
                                self.assertEqual(impl.successful_round(),window)
                            else:
                                threshold=max(value//2,2)
                                window=1
                                self.assertEqual(impl.timeout(value),(window,threshold))
                            self.assertEqual((impl.cwnd,impl.ssthresh),(window,threshold))
                            self.assertGreaterEqual(impl.cwnd,1)
                            self.assertGreaterEqual(impl.ssthresh,2)
                        examined+=1
            self.assertEqual(examined,3*sum(6**n for n in range(5)))

    def test_sender_limit_and_rejected_operations(self):
        for lang in ("en","pt"):
            cls=chapter(lang).RoundCongestionSketch
            for bad in (True,1,0,-1,1.5):
                with self.assertRaises(ValueError):cls(bad)
            clock=cls(8)
            for cwnd in range(1,12):
                clock.cwnd=cwnd
                for rwnd,flight in itertools.product(range(9),repeat=2):
                    available=sum(1 for _ in range(flight,min(cwnd,rwnd)))
                    self.assertEqual(clock.available(rwnd,flight),available)
            for invalid in ((-1,0),(0,-1),(True,0),(0,True),(1.5,1)):
                previous=(clock.cwnd,clock.ssthresh)
                with self.assertRaises(ValueError):clock.available(*invalid)
                self.assertEqual((clock.cwnd,clock.ssthresh),previous)
            for bad in (True,-1,1.5):
                previous=(clock.cwnd,clock.ssthresh)
                with self.assertRaises(ValueError):clock.timeout(bad)
                self.assertEqual((clock.cwnd,clock.ssthresh),previous)

if __name__=="__main__":
    unittest.main()
