"""Independent finite IPv4 bitmask and DNS-TTL event oracles for PT/EN chapters."""
import itertools
import re
import sys
import types
import unittest
from ipaddress import IPv4Address
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def published(lang):
    mod = types.ModuleType("_ip_dns_" + lang)
    sys.modules[mod.__name__] = mod
    try:
        body = load_articles()[lang]["ip-routing-dns-resolution"]["body"]
        code = tuple(FENCE.finditer(body))
        if len(code) != 2:
            raise AssertionError("expected two independently verifiable Python models")
        for i, match in enumerate(code, 1):
            exec(compile(match["code"], f"{lang}/ip_dns/fence-{i}", "exec"),
                 mod.__dict__, mod.__dict__)
    finally:
        sys.modules.pop(mod.__name__, None)
    return mod

def bitmask_oracle(routes, dest):
    """Independently match a 32-bit integer using bit masks, not IPv4Network."""
    dst = int(IPv4Address(dest))
    choices = []
    for index, (prefix, gateway, metric) in enumerate(routes):
        base, bits_text = prefix.split("/")
        bits = int(bits_text)
        mask = ((1 << bits) - 1) << (32 - bits) if bits else 0
        if (dst & mask) == (int(IPv4Address(base)) & mask):
            choices.append((bits, -metric, -index, prefix, gateway))
    if not choices:
        return None
    _, _, _, prefix, gateway = max(choices)
    return (prefix, gateway)

class IndependentPositiveCache:
    """Reference state evolves by event rules rather than using the chapter class."""
    def __init__(self):
        self.data = {}
        self.time = 0

    @staticmethod
    def key(name, kind):
        name = name[:-1] if name.endswith(".") else name
        return (name.lower(), kind)

    def put(self, name, kind, answers, ttl, when):
        self.time = when
        key = self.key(name, kind)
        if ttl == 0:
            self.data.pop(key, None)
            return False
        self.data[key] = (answers, when + ttl)
        return True

    def get(self, name, kind, when):
        self.time = when
        key = self.key(name, kind)
        result = self.data.get(key)
        if result is None:
            return None
        addresses, expiry = result
        if when >= expiry:
            del self.data[key]
            return None
        return (addresses, expiry - when)

ROUTES = (
    ("0.0.0.0/0", "198.51.100.1", 30),
    ("192.0.2.0/24", "198.51.100.2", 50),
    ("192.0.2.128/25", "198.51.100.3", 20),
    ("192.0.2.128/25", "198.51.100.4", 10),
    ("192.0.2.0/26", "198.51.100.5", 5),
    ("203.0.113.0/24", "198.51.100.6", 0),
)
DESTINATIONS = (
    "192.0.2.0", "192.0.2.1", "192.0.2.50", "192.0.2.63",
    "192.0.2.64", "192.0.2.127", "192.0.2.128", "192.0.2.200",
    "192.0.2.255", "203.0.113.10", "198.51.100.2", "127.0.0.1",
)
DNS_ACTIONS = (
    ("put", "WWW.Example.test.", "A", ("192.0.2.3",), 5),
    ("put", "www.example.test", "A", ("192.0.2.4",), 1),
    ("put", "WWW.EXAMPLE.TEST", "A", ("192.0.2.5",), 0),
    ("put", "www.example.test", "AAAA", ("2001:db8::1",), 4),
    ("get", "www.example.test", "A", (), 0),
    ("get", "WWW.Example.test.", "A", (), 0),
    ("get", "www.example.test", "AAAA", (), 0),
)

class NetworkingFoundationsContracts(unittest.TestCase):
    def test_ipv4_routes_against_bitmask_reference(self):
        for lang in ("en", "pt"):
            route = published(lang).choose_ipv4_route
            examined = 0
            for length in range(4):
                for entries in itertools.product(ROUTES, repeat=length):
                    for dest in DESTINATIONS:
                        self.assertEqual(route(entries, dest),
                                         bitmask_oracle(entries, dest),
                                         (lang, entries, dest))
                        examined += 1
            self.assertEqual(examined,
                             len(DESTINATIONS) * sum(len(ROUTES) ** k for k in range(4)))
            for bad_route in (("192.0.2.1/24", "198.51.100.1", 1),
                              ("192.0.2.0/24", "invalid", 1),
                              ("192.0.2.0/24", "198.51.100.1", True),
                              ("192.0.2.0/24", "198.51.100.1", -1)):
                with self.assertRaises(ValueError):
                    route([ROUTES[0], bad_route], "203.0.113.10")
            for dest in (True, "2001:db8::1", "bad"):
                with self.assertRaises(ValueError):
                    route([], dest)

    def test_positive_dns_cache_event_histories(self):
        for lang in ("en", "pt"):
            cls = published(lang).PositiveDnsCache
            histories = 0
            for length in range(6):
                for events in itertools.product(DNS_ACTIONS, repeat=length):
                    impl, ref = cls(), IndependentPositiveCache()
                    for step, (operation, name, kind, answers, ttl) in enumerate(events):
                        now = step * 2
                        if operation == "put":
                            self.assertEqual(impl.put(name, kind, answers, ttl, now),
                                             ref.put(name, kind, answers, ttl, now))
                        else:
                            self.assertEqual(impl.get(name, kind, now),
                                             ref.get(name, kind, now),
                                             (lang, events))
                        self.assertEqual(impl.entries, ref.data)
                        self.assertEqual(impl.last_time, ref.time)
                    histories += 1
            self.assertEqual(histories, sum(len(DNS_ACTIONS) ** k for k in range(6)))

    def test_ttl_boundaries_validation_and_nonmutation(self):
        for lang in ("en", "pt"):
            cls = published(lang).PositiveDnsCache
            cache = cls()
            self.assertTrue(cache.put("x.example.test.", "AAAA", ("2001:db8::1",), 3, 10))
            self.assertEqual(cache.get("X.EXAMPLE.TEST", "AAAA", 12),
                             (("2001:db8::1",), 1))
            self.assertIsNone(cache.get("x.example.test", "AAAA", 13))
            self.assertEqual(cache.entries, {})
            for bad in (
                ("x..example.test", "A", ("192.0.2.1",), 3, 13),
                ("x.example.test", "MX", ("192.0.2.1",), 3, 13),
                ("x.example.test", "A", ("2001:db8::1",), 3, 13),
                ("x.example.test", "AAAA", ("192.0.2.1",), 3, 13),
                ("x.example.test", "A", ("bad-ip",), 3, 13),
                ("x.example.test", "A", (), 3, 13),
                ("x.example.test", "A", ("192.0.2.1",), True, 13),
                ("x.example.test", "A", ("192.0.2.1",), -1, 13),
                ("x.example.test", "A", ("192.0.2.1",), 2, 12),
            ):
                state = (dict(cache.entries), cache.last_time)
                with self.assertRaises(ValueError):
                    cache.put(*bad)
                self.assertEqual((cache.entries, cache.last_time), state)
            with self.assertRaises(ValueError):
                cache.get("x.example.test", "A", 12)
            self.assertEqual(cache.last_time, 13)

if __name__ == "__main__":
    unittest.main()
