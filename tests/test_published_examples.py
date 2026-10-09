"""Execute self-contained Python examples in essential bilingual algorithm chapters."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ("binary-search", "heaps-priority-queues", "rate-limiting")

class PublishedExampleTests(unittest.TestCase):
    def test_python_examples_in_both_languages(self):
        for language in ("en", "pt"):
            for chapter in CHAPTERS:
                text = (ROOT/"content"/language/"topics"/f"{chapter}.md").read_text(encoding="utf-8")
                samples = re.findall(r"~~~python\n(.*?)\n~~~", text, re.S)
                self.assertTrue(samples, f"{language}/{chapter}: no executable example")
                for index, code in enumerate(samples):
                    with self.subTest(language=language, chapter=chapter, index=index):
                        exec(compile(code, f"{language}/{chapter}:{index}", "exec"), {})

if __name__ == "__main__":
    unittest.main()
