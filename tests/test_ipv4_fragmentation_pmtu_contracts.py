"""Independent finite byte-ownership and per-hop oracles for PT/EN IP models."""
import itertools
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles
FENCE = re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def article(lang):
    mod = types.ModuleType("_ipv4_pmtud_" + lang)
    sys.modules[mod.__name__] = mod
    try:
        body = load_articles()[lang]["ipv4-fragmentation-path-mtu"]["body"]
        fences = tuple(FENCE.finditer(body))
        assert len(fences) == 2
        for i, fence in enumerate(fences, 1):
            exec(compile(fence["code"], f"{lang}/ipv4/fence-{i}", "exec"),
                 mod.__dict__, mod.__dict__)
    finally:
        sys.modules.pop(mod.__name__, None)
    return mod

def expected_layout(size, mtu):
    capacity = mtu - 20
    if size <= capacity:
        return [(0, size, False)]
    aligned = capacity - (capacity % 8)
    cuts = range(0, size, aligned)
    return [(start, min(aligned, size - start),
             start + aligned < size) for start in cuts]

def byte_ownership(parts):
    final = [8 * part.offset_units + len(part.payload)
             for part in parts if not part.more]
    if len(final) != 1:
        raise ValueError("final count")
    filled = [None] * final[0]
    for part in parts:
        start = 8 * part.offset_units
        if start + len(part.payload) > len(filled):
            raise ValueError("out of bounds")
        if part.more and (not part.payload or len(part.payload) % 8):
            raise ValueError("misaligned")
        for position, value in enumerate(part.payload, start):
            if filled[position] is not None:
                raise ValueError("overlapping bytes")
            filled[position] = value
    if any(value is None for value in filled):
        raise ValueError("missing bytes")
    return bytes(filled)

def path_reference(hops, initial):
    attempted = initial
    result = []
    for _ in range(len(hops) + 1):
        failure = next(((i, limit) for i, limit in enumerate(hops)
                        if attempted > limit), None)
        if failure is None:
            return tuple(result + [(attempted, "delivered", None, None)])
        index, limit = failure
        result.append((attempted, "too-big", index, limit))
        attempted = limit
    raise AssertionError("failed to converge")

class IPv4PMTUContracts(unittest.TestCase):
    def test_fragment_bounds_and_reassembly_in_both_languages(self):
        for lang in ("en", "pt"):
            api = article(lang)
            for mtu in (68, 69, 70, 77, 79, 80, 100, 128):
                for length in range(257):
                    original = bytes(i % 256 for i in range(length))
                    parts = api.fragment_ipv4(original, mtu)
                    self.assertEqual(
                        [(p.offset_units * 8, len(p.payload), p.more) for p in parts],
                        expected_layout(length, mtu), (lang, mtu, length))
                    self.assertTrue(all(20 + len(p.payload) <= mtu for p in parts))
                    self.assertEqual(byte_ownership(parts[::-1]), original)
                    self.assertEqual(api.reassemble_ipv4(parts[::-1]), original)
                    if length > mtu - 20:
                        with self.assertRaises(ValueError):
                            api.fragment_ipv4(original, mtu, True)
                    else:
                        self.assertEqual(
                            api.fragment_ipv4(original, mtu, True),
                            (api.Fragment(0, False, original),))
            payload = bytes(i % 256 for i in range(65515))
            self.assertEqual(
                api.reassemble_ipv4(api.fragment_ipv4(payload, 68)), payload)

    def test_invalid_records_and_arguments(self):
        for lang in ("en", "pt"):
            api = article(lang)
            F = api.Fragment
            bad_sets = (
                (), (F(0, True, b"12345678"),),
                (F(1, False, b"x"),),
                (F(0, False, b"x"), F(0, False, b"x")),
                (F(0, True, b"short"), F(1, False, b"x")),
                (F(0, True, b"12345678"), F(0, False, b"x")),
                (F(0, True, b"12345678"), F(2, False, b"x")),
                (F(-1, False, b"x"),), (F(True, False, b"x"),),
                (F(8192, False, b"x"),),
                (F(0, False, bytearray(b"x")),),
            )
            for parts in bad_sets:
                with self.subTest(lang=lang, parts=repr(parts)[:100]):
                    with self.assertRaises(ValueError):
                        api.reassemble_ipv4(parts)
            bad_args = (
                (b"abc", 67, False), (b"abc", True, False),
                (b"abc", 65536, False), ("bad", 68, False),
                (b"a", 68, 1), (bytes(65516), 1500, False),
            )
            for args in bad_args:
                with self.assertRaises(ValueError):
                    api.fragment_ipv4(*args)

    def test_independent_path_probes(self):
        values = (68, 100, 120, 500, 1500)
        for lang in ("en", "pt"):
            api = article(lang)
            for n in range(1, 4):
                for hops in itertools.product(values, repeat=n):
                    for initial in (68, 90, 110, 130, 600, 1500):
                        trace = api.classical_pmtud_trace(hops, initial)
                        self.assertEqual(trace, path_reference(hops, initial))
                        self.assertEqual(trace[-1][0], min(initial, *hops))
                        self.assertTrue(all(
                            trace[i+1][0] < trace[i][0]
                            for i in range(len(trace) - 1)))
            for path, size in (
                ((), 200), ((67,), 200), ((True,), 200),
                ((100,), True), ((100,), 65536), ((100,), 19)):
                with self.assertRaises(ValueError):
                    api.probe_df_path(path, size)

if __name__ == "__main__":
    unittest.main()
