"""Cross-check resizing-array amortization and a bounded instructional CPU."""
from pathlib import Path
import random
import re
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

PYTHON_FENCES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def execute_chapter(lang, slug):
    source = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf8")
    snippets = PYTHON_FENCES.findall(source)
    if not snippets:
        raise AssertionError(f"missing executable Python example: {lang}/{slug}")
    module = types.ModuleType(f"chapter_{lang}_{slug.replace('-', '_')}")
    sys.modules[module.__name__] = module
    try:
        for snippet in snippets:
            exec(compile(snippet, module.__name__, "exec"), module.__dict__)
        return module.__dict__
    finally:
        sys.modules.pop(module.__name__, None)

def cpu_reference_step(memory, pc, accumulator, halted):
    if halted:
        raise RuntimeError("halted")
    if not 0 <= pc < 16:
        raise IndexError("bad pc")
    instruction = memory[pc]
    opcode, operand = divmod(instruction, 16)
    if opcode not in (1, 2, 3, 4, 5, 6, 15) or (opcode == 15 and operand):
        raise ValueError("bad opcode")
    next_memory = list(memory)
    next_acc = accumulator
    next_pc = pc + 1
    if opcode == 1:
        next_acc = memory[operand]
    if opcode == 2:
        next_memory[operand] = accumulator
    if opcode == 3:
        next_acc = (accumulator + memory[operand]) & 255
    if opcode == 4 and accumulator:
        next_pc = operand
    if opcode == 5:
        next_acc = operand
    if opcode == 6:
        next_acc = (accumulator - memory[operand]) & 255
    return next_memory, next_pc, next_acc, opcode == 15

class ResizingArrayTests(unittest.TestCase):
    def test_against_list_under_mixed_adversarial_updates(self):
        for lang in ("en", "pt"):
            Array = execute_chapter(lang, "resizable-arrays-capacity-amortized-cost")["ResizingArray"]
            a, oracle = Array(), []
            rng = random.Random(73621)
            for index in range(2400):
                if not oracle or rng.randrange(5) != 0:
                    value = None if index % 9 == 0 else rng.randrange(-30, 31)
                    a.append(value)
                    oracle.append(value)
                else:
                    self.assertEqual(a.pop(), oracle.pop())
                self.assertEqual(len(a), len(oracle))
                self.assertEqual(a.snapshot(), tuple(oracle))
                self.assertGreaterEqual(a.capacity, max(1, len(a)))
                self.assertEqual(a.capacity & (a.capacity - 1), 0)
                self.assertTrue(all(slot is None for slot in a._slots[len(a):]))
                if oracle:
                    self.assertEqual(a.get(0), oracle[0])
                    self.assertEqual(a.get(len(oracle) - 1), oracle[-1])
            while oracle:
                self.assertEqual(a.pop(), oracle.pop())
            self.assertEqual((a.capacity, len(a)), (1, 0))
            self.assertLessEqual(a.moves, 8 * 4800)
            old = (a.capacity, a.snapshot(), a.moves)
            with self.assertRaises(IndexError):
                a.pop()
            with self.assertRaises(IndexError):
                a.get(False)
            self.assertEqual((a.capacity, a.snapshot(), a.moves), old)

    def test_capacity_boundaries_and_hysteresis(self):
        for lang in ("en", "pt"):
            Array = execute_chapter(lang, "resizable-arrays-capacity-amortized-cost")["ResizingArray"]
            a = Array()
            caps = []
            for i in range(9):
                a.append(i)
                caps.append(a.capacity)
            self.assertEqual(caps, [1, 2, 4, 4, 8, 8, 8, 8, 16])
            self.assertEqual(a.snapshot(), tuple(range(9)))
            for i in reversed(range(9)):
                self.assertEqual(a.pop(), i)
            self.assertEqual(a.capacity, 1)
            self.assertLessEqual(a.moves, 8 * 18)

class DatapathTests(unittest.TestCase):
    def test_single_step_exhaustive_instruction_encodings(self):
        for lang in ("en", "pt"):
            Cpu = execute_chapter(lang, "cpu-datapath-fetch-decode-execute")["TinyCPU"]
            for instruction in range(256):
                for acc in (0, 1, 255):
                    ram = [17] * 16
                    ram[0] = instruction
                    ram[1] = 3
                    cpu = Cpu(ram)
                    cpu.acc = acc
                    before = (list(cpu.memory), cpu.pc, cpu.acc, cpu.halted)
                    try:
                        expected = cpu_reference_step(ram, 0, acc, False)
                    except ValueError:
                        with self.assertRaises(ValueError):
                            cpu.step()
                        self.assertEqual((cpu.memory, cpu.pc, cpu.acc, cpu.halted), before)
                    else:
                        trace = cpu.step()
                        self.assertEqual((cpu.memory, cpu.pc, cpu.acc, cpu.halted), expected)
                        self.assertEqual(trace, (0, instruction >> 4, instruction & 15,
                                                 expected[1], expected[2]))
            with self.assertRaises(ValueError):
                Cpu([0] * 15)
            with self.assertRaises(ValueError):
                Cpu([0] * 15 + [True])
            halted = Cpu([0xF0] + [0] * 15)
            halted.step()
            with self.assertRaises(RuntimeError):
                halted.step()

    def test_bounded_counter_program(self):
        for lang in ("en", "pt"):
            Cpu = execute_chapter(lang, "cpu-datapath-fetch-decode-execute")["TinyCPU"]
            for count in (1, 2, 3, 8, 15):
                ram = [0x50 | count, 0x2F, 0x1F, 0x6E, 0x2F, 0x42, 0xF0]
                ram += [0] * 7 + [1, 0]
                cpu = Cpu(ram)
                steps = 0
                while not cpu.halted and steps < 100:
                    cpu.step()
                    steps += 1
                self.assertTrue(cpu.halted)
                self.assertEqual(steps, 3 + 4 * count)
                self.assertEqual((cpu.acc, cpu.memory[15], cpu.pc), (0, 0, 7))
            bad = Cpu([0x50] * 16)
            for _ in range(16):
                bad.step()
            self.assertEqual(bad.pc, 16)
            with self.assertRaises(IndexError):
                bad.step()

class CurriculumIntegrityTests(unittest.TestCase):
    def test_bilingual_prerequisites_and_order(self):
        modules = load_modules()
        articles = load_articles()
        self.assertEqual(modules["resizable-arrays-capacity-amortized-cost"], "algorithms")
        self.assertEqual(modules["cpu-datapath-fetch-decode-execute"], "computer-architecture")
        for slug in ("resizable-arrays-capacity-amortized-cost", "cpu-datapath-fetch-decode-execute"):
            self.assertEqual(articles["en"][slug]["meta"]["prerequisites"],
                             articles["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            slugs = [slug for section in track["sections"] for slug in section["articles"]]
            for before, after in (
                ("arrays-and-strings", "resizable-arrays-capacity-amortized-cost"),
                ("abstract-data-types-representation-invariants",
                 "resizable-arrays-capacity-amortized-cost"),
                ("sequential-logic-registers-state-machines",
                 "cpu-datapath-fetch-decode-execute"),
                ("machine-representation-isa-cache", "cpu-datapath-fetch-decode-execute"),
                ("cpu-datapath-fetch-decode-execute", "cpu-pipeline-hazards-branch-prediction"),
            ):
                self.assertLess(slugs.index(before), slugs.index(after))
            self.assertEqual(len(slugs), len(set(slugs)))

if __name__ == "__main__":
    unittest.main()
