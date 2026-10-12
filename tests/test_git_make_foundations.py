"""Git state contracts and GNU Make dependency-graph tests, with real CLI tools."""
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

C_BLOCKS = re.compile(r"(?ms)^~~~c\n// file: ([A-Za-z0-9_.-]+)\n(.*?)^~~~[ \t]*$")
MAKE_BLOCK = re.compile(r"(?ms)^~~~make\n# file: Makefile\n(.*?)^~~~[ \t]*$")

def source(lang, slug):
    return (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf-8")

def command(argv, cwd, env=None):
    return subprocess.run(argv, cwd=cwd, env=env, text=True,
                          capture_output=True, check=False, timeout=20)

class GitFoundationTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("Git executable not installed")

    def test_staged_snapshot_independent_of_later_edit(self):
        for lang in ("en", "pt"):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)
                env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                       "GIT_CONFIG_GLOBAL": os.devnull}
                def run(*args):
                    result = command(["git", *args], cwd=tmp, env=env)
                    self.assertEqual(result.returncode, 0,
                                     f"{args}: {result.stderr}")
                    return result.stdout
                run("init", "-q")
                run("config", "user.name", "Isolated Git Test")
                run("config", "user.email", "test@example.invalid")
                (p / "note.txt").write_text("A\n")
                run("add", "--", "note.txt")
                run("commit", "-q", "-m", "initial")
                (p / "note.txt").write_text("B\n")
                run("add", "--", "note.txt")
                (p / "note.txt").write_text("C\n")
                self.assertEqual(run("show", ":note.txt"), "B\n")
                self.assertEqual(run("show", "HEAD:note.txt"), "A\n")
                self.assertEqual((p / "note.txt").read_text(), "C\n")
                self.assertIn("B", run("diff", "--cached"))
                self.assertIn("C", run("diff"))
                run("commit", "-q", "-m", "staged snapshot")
                self.assertEqual(run("show", "HEAD:note.txt"), "B\n")
                self.assertEqual((p / "note.txt").read_text(), "C\n")
                run("restore", "--staged", "--", "note.txt")
                self.assertEqual((p / "note.txt").read_text(), "C\n")
                self.assertIn("C", run("diff"))
                self.assertIn("index", source(lang, "git-version-control-commits-branches").lower())

    def test_two_parent_merge_and_clean_worktree(self):
        for lang in ("en", "pt"):
            self.assertIn("git merge", source(lang, "git-version-control-commits-branches"))
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)
                env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                       "GIT_CONFIG_GLOBAL": os.devnull}
                def run(*args):
                    result = command(["git", *args], cwd=tmp, env=env)
                    self.assertEqual(result.returncode, 0,
                                     f"{args}: {result.stderr}")
                    return result.stdout
                run("init", "-q")
                run("config", "user.name", "Isolated Git Test")
                run("config", "user.email", "test@example.invalid")
                (p / "note.txt").write_text("first\n")
                run("add", "--", "note.txt")
                run("commit", "-q", "-m", "initial")
                run("branch", "-M", "main")
                run("switch", "-q", "-c", "edit")
                (p / "note.txt").write_text("second\n")
                run("add", "--", "note.txt")
                run("commit", "-q", "-m", "edit")
                run("switch", "-q", "main")
                run("merge", "-q", "--no-ff", "-m", "merge edit", "edit")
                parents = run("rev-list", "--parents", "-n", "1", "HEAD").strip().split()
                self.assertEqual(len(parents), 3)
                self.assertEqual((p / "note.txt").read_text(), "second\n")
                self.assertEqual(run("status", "--porcelain"), "")

class BuildDependencyTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("make") or not (shutil.which("cc") or shutil.which("gcc")):
            self.skipTest("GNU make or C compiler unavailable")

    def test_c_compilation_rebuild_phony_and_clean(self):
        for lang in ("en", "pt"):
            txt = source(lang, "build-dependency-graphs-gnu-make")
            files = dict(C_BLOCKS.findall(txt))
            make = MAKE_BLOCK.findall(txt)
            self.assertEqual(set(files), {"math_ops.h", "math_ops.c", "main.c"})
            self.assertEqual(len(make), 1)
            self.assertIn("\t$(CC)", make[0], "Recipes must use real TAB characters")
            self.assertIn("main.o: main.c math_ops.h", make[0])
            self.assertIn("math_ops.o: math_ops.c math_ops.h", make[0])
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)
                for filename, code in files.items():
                    (p / filename).write_text(code, encoding="utf8")
                (p / "Makefile").write_text(make[0], encoding="utf8")
                built = command(["make", "demo"], cwd=tmp)
                self.assertEqual(built.returncode, 0, built.stderr)
                self.assertEqual(command([str(p / "demo")], cwd=tmp).stdout,
                                 "answer=42\n")
                noop = command(["make", "-n", "demo"], cwd=tmp)
                self.assertEqual(noop.returncode, 0, noop.stderr)
                self.assertNotIn(" -c ", noop.stdout)
                self.assertNotIn(" -o demo", noop.stdout)
                stamps = [(p / item).stat().st_mtime_ns
                          for item in ("math_ops.h", "main.o", "math_ops.o", "demo")]
                future = max(stamps) + 3_000_000_000
                os.utime(p / "math_ops.h", ns=(future, future))
                rebuild = command(["make", "-n", "demo"], cwd=tmp)
                self.assertEqual(rebuild.returncode, 0, rebuild.stderr)
                self.assertIn("-c main.c", rebuild.stdout)
                self.assertIn("-c math_ops.c", rebuild.stdout)
                self.assertIn("main.o math_ops.o -o demo", rebuild.stdout)
                changed = command(["make", "demo"], cwd=tmp)
                self.assertEqual(changed.returncode, 0, changed.stderr)
                (p / "check").write_text("not a real target\n")
                checked = command(["make", "check"], cwd=tmp)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertIn("answer=42", checked.stdout)
                clean = command(["make", "clean"], cwd=tmp)
                self.assertEqual(clean.returncode, 0, clean.stderr)
                for name in ("demo", "main.o", "math_ops.o"):
                    self.assertFalse((p / name).exists())

class LearningPathTests(unittest.TestCase):
    def test_bilingual_parity_and_prerequisite_order(self):
        modules = load_modules()
        articles = load_articles()
        for topic in ("git-version-control-commits-branches",
                      "build-dependency-graphs-gnu-make"):
            self.assertEqual(modules[topic], "engineering")
            self.assertEqual(articles["en"][topic]["meta"]["prerequisites"],
                             articles["pt"][topic]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            names = [name for section in track["sections"] for name in section["articles"]]
            for left, right in (
                ("modular-programming-interfaces", "git-version-control-commits-branches"),
                ("git-version-control-commits-branches", "build-dependency-graphs-gnu-make"),
                ("c-compilation-object-files-linking", "build-dependency-graphs-gnu-make"),
                ("build-dependency-graphs-gnu-make",
                 "process-cli-arguments-environment-exit-status"),
            ):
                self.assertLess(names.index(left), names.index(right))
            self.assertEqual(len(names), len(set(names)))

if __name__ == "__main__":
    unittest.main()
