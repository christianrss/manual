"""Independent finite tests for the PT/EN RFC 5869 + TLS 1.3 teaching chapter.

The oracle HMAC performs ipad/opad SHA-256 manually instead of importing
hmac.new, and the TLS label oracle uses struct packing rather than the
article's byte concatenation. None of these tests implement TLS.
"""
import hashlib
import itertools
import re
import struct
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang):
    mod = types.ModuleType("_tls13_hkdf_" + lang)
    sys.modules[mod.__name__] = mod
    try:
        body = load_articles()[lang]["tls13-hkdf-handshake"]["body"]
        matches = tuple(FENCE.finditer(body))
        if len(matches) != 2:
            raise AssertionError("expected exactly two executable Python examples")
        for index, match in enumerate(matches, 1):
            exec(compile(match["code"], f"{lang}/tls13/fence-{index}", "exec"),
                 mod.__dict__, mod.__dict__)
    finally:
        sys.modules.pop(mod.__name__, None)
    return mod

def sha256_hmac_without_hmac_module(key, content):
    # RFC 2104 construction, SHA-256 block length 64.
    if len(key) > 64:
        key = hashlib.sha256(key).digest()
    key = key.ljust(64, b"\x00")
    inner_key = bytes(x ^ 0x36 for x in key)
    outer_key = bytes(x ^ 0x5c for x in key)
    inner = hashlib.sha256(inner_key + content).digest()
    return hashlib.sha256(outer_key + inner).digest()

def reference_extract(salt, ikm):
    return sha256_hmac_without_hmac_module(salt if salt else bytes(32), ikm)

def reference_expand(prk, info, length):
    # Independent while-loop implementation; no call to chapter's expand.
    result = bytearray()
    prior = b""
    counter = 1
    while len(result) < length:
        prior = sha256_hmac_without_hmac_module(
            prk, prior + info + counter.to_bytes(1, "big"))
        result.extend(prior)
        counter += 1
    return bytes(result[:length])

def reference_label(label, context, length):
    prefixed = b"tls13 " + label.encode("ascii")
    return (struct.pack("!H", length)
            + struct.pack("!B", len(prefixed)) + prefixed
            + struct.pack("!B", len(context)) + context)

class TLS13HKDFContractTests(unittest.TestCase):
    def test_rfc5869_known_answer_vectors(self):
        # Case 1 and case 3 are taken from RFC 5869 Appendix A (SHA-256).
        cases = (
            (
                bytes(range(13)), bytes([11]) * 22,
                bytes(range(240, 250)), 42,
                "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5",
                "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
            ),
            (
                b"", bytes([11]) * 22, b"", 42,
                "19ef24a32c717b167f33a91d6f648bdf96596776afdb6377ac434c1c293ccb04",
                "8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8"
            ),
        )
        for lang in ("en", "pt"):
            mod = chapter(lang)
            for salt, ikm, info, length, prk_hex, okm_hex in cases:
                prk = mod.hkdf_extract(salt, ikm)
                self.assertEqual(prk.hex(), prk_hex)
                self.assertEqual(mod.hkdf_expand(prk, info, length).hex(), okm_hex)

    def test_exhaustive_small_inputs_against_manual_hmac(self):
        salts = (b"", b"x", bytes(range(13)), bytes(range(72)))
        input_material = (b"", b"\x00", b"secret", bytes(range(80)))
        infos = (b"", b"key", b"context", bytes(range(64)))
        lengths = (0, 1, 2, 31, 32, 33, 42, 63, 64, 65, 95)
        for lang in ("en", "pt"):
            mod = chapter(lang)
            tested = 0
            for salt, ikm, info, length in itertools.product(
                    salts, input_material, infos, lengths):
                prk = mod.hkdf_extract(salt, ikm)
                self.assertEqual(prk, reference_extract(salt, ikm))
                self.assertEqual(mod.hkdf_expand(prk, info, length),
                                 reference_expand(prk, info, length))
                self.assertEqual(len(mod.hkdf_expand(prk, info, length)), length)
                tested += 1
            self.assertEqual(tested, len(salts)*len(input_material)*len(infos)*len(lengths))
            # Validate counter boundary at the maximum 255 HMAC blocks.
            maximal = mod.hkdf_expand(bytes(32), b"max", 8160)
            self.assertEqual(len(maximal), 8160)
            self.assertEqual(maximal, reference_expand(bytes(32), b"max", 8160))

    def test_independent_tls_label_serialization_and_output(self):
        labels = ("key", "iv", "finished", "c ap traffic", "a"*249)
        contexts = (b"", b"\x00", b"data", bytes(range(255)))
        lengths = (0, 1, 12, 16, 32, 42, 255)
        secret = hashlib.sha256(b"fixed public teaching secret").digest()
        for lang in ("en", "pt"):
            mod = chapter(lang)
            count = 0
            for label, context, length in itertools.product(labels, contexts, lengths):
                expected_info = reference_label(label, context, length)
                actual_info = mod.tls13_hkdf_label(label, context, length)
                self.assertEqual(actual_info, expected_info)
                expected_output = reference_expand(secret, expected_info, length)
                self.assertEqual(mod.tls13_expand_label(secret, label, context, length),
                                 expected_output)
                count += 1
            self.assertEqual(count, len(labels)*len(contexts)*len(lengths))
            self.assertEqual(mod.tls13_hkdf_label("key", b"", 16).hex(),
                             "001009746c733133206b657900")

    def test_invalid_inputs_rejected_without_hidden_coercion(self):
        for lang in ("en", "pt"):
            mod = chapter(lang)
            for salt, ikm in ((None, b"ikm"), (b"salt", "not bytes"),
                              (bytearray(b"s"), b"ikm")):
                with self.assertRaises(ValueError):
                    mod.hkdf_extract(salt, ikm)
            for prk, info, length in (
                (bytes(31), b"", 1), (bytes(32), "bad", 1),
                (bytes(32), b"", -1), (bytes(32), b"", True),
                (bytes(32), b"", 8161), (None, b"", 1)):
                with self.assertRaises(ValueError):
                    mod.hkdf_expand(prk, info, length)
            for label, context, length in (
                ("", b"", 1), ("é", b"", 1), ("x"*250, b"", 1),
                ("key", "not bytes", 16), ("key", bytes(256), 16),
                ("key", b"", True), ("key", b"", -1),
                ("key", b"", 65536)):
                with self.assertRaises(ValueError):
                    mod.tls13_hkdf_label(label, context, length)
            # Label encoding permits 65535 in its uint16 field, but
            # SHA-256 HKDF still caps the *derived output* to 8160 bytes.
            self.assertEqual(
                mod.tls13_hkdf_label("key", b"", 65535)[:2], b"\xff\xff")
            with self.assertRaises(ValueError):
                mod.tls13_expand_label(bytes(32), "key", b"", 8161)

if __name__ == "__main__":
    unittest.main()
