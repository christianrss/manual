"""Integration contracts for two bilingual C toolchain/CLI foundation lessons."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

BLOCKS = re.compile(r"(?ms)^~~~c\n// file: ([a-zA-Z0-9_.-]+)\n(.*?)^~~~[ \t]*$")

def extract(lang, slug):
    content = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf8")
    matches = BLOCKS.findall(content)
    if not matches:
        raise AssertionError("No C code samples in " + slug)
    return dict(matches)

def call(argv, cwd=None, env=None):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                          text=True, check=False, timeout=15)

class CNativeToolchainContracts(unittest.TestCase):
    def setUp(self):
        self.compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not self.compiler:
            self.skipTest("C11 compiler is unavailable")

    def test_compilation_stages_and_link_failures(self):
        for lang in ("en", "pt"):
            parts = extract(lang, "c-compilation-object-files-linking")
            self.assertEqual(set(parts), {"math_ops.h", "math_ops.c", "main.c"})
            with tempfile.TemporaryDirectory() as tmp:
                wd = Path(tmp)
                for name, body in parts.items():
                    (wd / name).write_text(body, encoding="utf8")
                flags = [self.compiler, "-std=c11", "-Wall", "-Wextra",
                         "-Werror", "-pedantic"]
                commands = [
                    flags + ["-E", "main.c", "-o", "main.i"],
                    flags + ["-S", "math_ops.c", "-o", "math_ops.s"],
                    flags + ["-c", "main.c", "-o", "main.o"],
                    flags + ["-c", "math_ops.c", "-o", "math_ops.o"],
                ]
                for command in commands:
                    result = call(command, cwd=tmp)
                    self.assertEqual(result.returncode, 0,
                                     f"{lang} {command}: {result.stderr}")
                for name in ("main.i", "math_ops.s", "main.o", "math_ops.o"):
                    self.assertTrue((wd / name).stat().st_size > 0, name)
                missing = call([self.compiler, "main.o", "-o", "bad"], cwd=tmp)
                self.assertNotEqual(missing.returncode, 0,
                                    "Caller linked without function definition")
                linked = call([self.compiler, "main.o", "math_ops.o",
                               "-o", "demo"], cwd=tmp)
                self.assertEqual(linked.returncode, 0, linked.stderr)
                executed = call([str(wd / "demo")], cwd=tmp)
                self.assertEqual(executed.returncode, 0, executed.stderr)
                self.assertEqual(executed.stdout, "result=42\n")
                self.assertEqual(executed.stderr, "")

    def test_process_args_environment_streams_and_status(self):
        for lang in ("en", "pt"):
            parts = extract(lang, "process-cli-arguments-environment-exit-status")
            self.assertEqual(set(parts), {"cli.c"})
            with tempfile.TemporaryDirectory() as tmp:
                wd = Path(tmp)
                (wd / "cli.c").write_text(parts["cli.c"], encoding="utf8")
                exe = wd / "cli"
                compiled = call([self.compiler, "-std=c11", "-Wall", "-Wextra",
                                 "-Werror", "-pedantic", "cli.c", "-o", str(exe)],
                                cwd=tmp)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                env = dict(os.environ)
                env.pop("MANUAL_EXAMPLE_MODE", None)
                for args, code, out, err in (
                    (["0"], 0, "next=1\n", ""),
                    (["42"], 0, "next=43\n", ""),
                    (["100"], 0, "next=101\n", ""),
                    ([], 2, "", "usage: cli NUMBER\n"),
                    (["1", "2"], 2, "", "usage: cli NUMBER\n"),
                    ([""], 3, "", "invalid NUMBER\n"),
                    (["-1"], 3, "", "invalid NUMBER\n"),
                    (["101"], 3, "", "invalid NUMBER\n"),
                    (["5oops"], 3, "", "invalid NUMBER\n"),
                    (["9999999999999999999999999999999"], 3, "", "invalid NUMBER\n"),
                ):
                    with self.subTest(lang=lang, args=args):
                        result = call([str(exe), *args], cwd=tmp, env=env)
                        self.assertEqual((result.returncode, result.stdout, result.stderr),
                                         (code, out, err))
                verbose = dict(env, MANUAL_EXAMPLE_MODE="verbose")
                result = call([str(exe), "42"], cwd=tmp, env=verbose)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, "next=43\n", "mode=verbose\n"))

class CNativeCurriculumIntegrity(unittest.TestCase):
    def test_track_positions_and_translation_prerequisites(self):
        modules = load_modules()
        self.assertEqual(modules["c-compilation-object-files-linking"], "foundations")
        self.assertEqual(modules["process-cli-arguments-environment-exit-status"],
                         "operating-systems")
        articles = load_articles()
        for name in ("c-compilation-object-files-linking",
                     "process-cli-arguments-environment-exit-status"):
            self.assertEqual(articles["en"][name]["meta"]["prerequisites"],
                             articles["pt"][name]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            slugs = [name for sec in track["sections"] for name in sec["articles"]]
            for earlier, later in (
                ("c-pointers-arrays-object-lifetimes",
                 "c-compilation-object-files-linking"),
                ("modular-programming-interfaces",
                 "c-compilation-object-files-linking"),
                ("c-compilation-object-files-linking",
                 "process-cli-arguments-environment-exit-status"),
                ("process-cli-arguments-environment-exit-status",
                 "processes-virtual-memory"),
            ):
                self.assertLess(slugs.index(earlier), slugs.index(later))
            self.assertEqual(len(slugs), len(set(slugs)))

if __name__ == "__main__":
    unittest.main()
