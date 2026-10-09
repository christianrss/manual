"""Execute every published Python example in order within its own chapter namespace.

Code fences of either common Markdown style are evaluated, with no dependency
on a different language's snippets. This catches undefined names introduced by
a translation and syntax errors masked by the HTML builder.
"""
from __future__ import annotations
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles  # noqa: E402

PYTHON_FENCE = re.compile(
    r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$"
)

class ChapterCodeExamples(unittest.TestCase):
    def test_all_python_fences_in_both_languages(self):
        articles = load_articles()
        executed = 0
        for lang in ("en", "pt"):
            for ident, article in sorted(articles[lang].items()):
                namespace = {"__name__": "__chapter_example__"}
                for index, match in enumerate(PYTHON_FENCE.finditer(article["body"]), 1):
                    with self.subTest(lang=lang, chapter=ident, block=index):
                        filename = f"{lang}/{ident}/code-{index}.py"
                        compiled = compile(match.group("code"), filename, "exec")
                        exec(compiled, namespace, namespace)
                    executed += 1
        self.assertGreaterEqual(executed, 20, "Unexpectedly few executable examples")

if __name__ == "__main__":
    unittest.main()
