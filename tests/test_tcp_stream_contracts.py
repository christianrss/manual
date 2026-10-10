"""Independent finite-state tests for published PT/EN TCP teaching models."""
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

def chapter(lang):
    module=types.ModuleType("_tcp_stream_"+lang)
    sys.modules[module.__name__]=module
    try:
        body=load_articles()[lang]["tcp-byte-stream-framing-flow-control"]["body"]
        snippets=tuple(FENCE.finditer(body))
        if len(snippets)!=2:
            raise AssertionError("expected two Python code blocks")
        for i,match in enumerate(snippets,1):
            exec(compile(match["code"],f"{lang}/tcp/fence-{i}","exec"),
                 module.__dict__,module.__dict__)
    finally:
        sys.modules.pop(module.__name__,None)
    return module

class IndexedOracle:
    """Per-position array independent of the chapter's pending dictionary."""
    def __init__(self,window):
        self.window=window
        self.ack=0
        self.cells=[None]*128
        self.delivered=bytearray()

    def accept(self,seq,payload):
        initial_ack=self.ack
        for delta,octet in enumerate(payload):
            index=seq+delta
            if initial_ack<=index<initial_ack+self.window and self.cells[index] is None:
                self.cells[index]=octet
        new=bytearray()
        while self.ack<len(self.cells) and self.cells[self.ack] is not None:
            new.append(self.cells[self.ack])
            self.cells[self.ack]=None
            self.ack+=1
        self.delivered.extend(new)
        return self.ack,bytes(new)

    def pending(self):
        return {i:octet for i,octet in enumerate(self.cells) if octet is not None}

class TCPStreamContractTests(unittest.TestCase):
    def test_every_frame_partition_of_short_message_sequences(self):
        payloads=(b"",b"A",b"\x00B")
        for lang in ("en","pt"):
            mod=chapter(lang)
            examined=0
            for length in range(4):
                for frames in itertools.product(payloads,repeat=length):
                    wire=b"".join(mod.encode_frame(part) for part in frames)
                    for cut1 in range(len(wire)+1):
                        for cut2 in range(cut1,len(wire)+1):
                            parser=mod.FrameDecoder(8)
                            received=[]
                            for chunk in (wire[:cut1],wire[cut1:cut2],wire[cut2:]):
                                received.extend(parser.feed(chunk))
                            self.assertEqual(tuple(received),frames,(lang,frames,cut1,cut2))
                            self.assertEqual(parser.buffer,bytearray())
                            examined+=1
                    parser=mod.FrameDecoder(8)
                    received=[]
                    for octet in wire:
                        received.extend(parser.feed(bytes((octet,))))
                    self.assertEqual(tuple(received),frames)
                    self.assertEqual(parser.buffer,bytearray())
            self.assertGreater(examined,1500)

    def test_frame_validation_and_rejected_feed_state(self):
        for lang in ("en","pt"):
            mod=chapter(lang)
            for invalid in ("text",bytearray(b"A"),None):
                with self.assertRaises(ValueError):mod.encode_frame(invalid)
            with self.assertRaises(ValueError):mod.encode_frame(bytes(65536))
            for maximum in (-1,True,65536,1.5):
                with self.assertRaises(ValueError):mod.FrameDecoder(maximum)
            parser=mod.FrameDecoder(8)
            self.assertEqual(parser.feed(b"\x00"),())
            previous=bytes(parser.buffer)
            with self.assertRaises(ValueError):parser.feed(b"\x09")
            self.assertEqual(bytes(parser.buffer),previous)
            with self.assertRaises(ValueError):parser.feed("invalid")
            self.assertEqual(bytes(parser.buffer),previous)
            self.assertEqual(parser.feed(b"\x01Z"),(b"Z",))
            self.assertEqual(parser.buffer,bytearray())
            with self.assertRaises(ValueError):
                parser.feed(mod.encode_frame(b"A")+b"\x00\x09")
            self.assertEqual(parser.buffer,bytearray())

    def test_out_of_order_relative_ack_against_index_oracle(self):
        events=((0,b"A"),(1,b"B"),(2,b"C"),(0,b"AB"),
                (2,b"CD"),(4,b"EF"),(1,b"BC"),(6,b"G"))
        for lang in ("en","pt"):
            mod=chapter(lang)
            cases=0
            for window in (2,4,8):
                for length in range(5):
                    for trace in itertools.product(events,repeat=length):
                        actual=mod.ToyReceiver(window)
                        oracle=IndexedOracle(window)
                        for segment in trace:
                            self.assertEqual(actual.accept(*segment),
                                             oracle.accept(*segment),
                                             (lang,window,trace))
                            self.assertEqual(actual.next_seq,oracle.ack)
                            self.assertEqual(dict(actual.pending),oracle.pending())
                            self.assertEqual(bytes(actual.delivered),
                                             bytes(oracle.delivered))
                        cases+=1
            self.assertEqual(cases,3*sum(8**n for n in range(5)))

    def test_receiver_validation_has_no_side_effects(self):
        for lang in ("en","pt"):
            mod=chapter(lang)
            for bad in (0,-1,True,1.5):
                with self.assertRaises(ValueError):mod.ToyReceiver(bad)
            receiver=mod.ToyReceiver(4)
            self.assertEqual(receiver.accept(2,b"CD"),(0,b""))
            old=(receiver.next_seq,dict(receiver.pending),bytes(receiver.delivered))
            for seq,payload in ((-1,b"A"),(True,b"A"),(0,"A"),
                                (0,bytearray(b"A")),(0.5,b"A")):
                with self.assertRaises(ValueError):
                    receiver.accept(seq,payload)
                self.assertEqual((receiver.next_seq,dict(receiver.pending),
                                  bytes(receiver.delivered)),old)
            self.assertEqual(receiver.accept(0,b"AB"),(4,b"ABCD"))

    def test_sender_window_allowance_is_bounded(self):
        for lang in ("en","pt"):
            fn=chapter(lang).send_allowance
            for cwnd,rwnd,flight in itertools.product(range(9),repeat=3):
                # Count slots directly, independent of the published formula.
                available=sum(1 for _ in range(flight,min(cwnd,rwnd)))
                self.assertEqual(fn(cwnd,rwnd,flight),available)
            for vals in ((-1,2,0),(2,True,1),(3,3,-1),(1.5,3,1)):
                with self.assertRaises(ValueError):fn(*vals)

if __name__=="__main__":
    unittest.main()
