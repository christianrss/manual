"""Independent finite oracles for EN/PT pipeline timing and prediction examples."""
import itertools
import re
import sys
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles

FENCE=re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def published(lang):
    module=types.ModuleType("_pipeline_"+lang)
    sys.modules[module.__name__]=module
    try:
        body=load_articles()[lang]["cpu-pipeline-hazards-branch-prediction"]["body"]
        for i,match in enumerate(FENCE.finditer(body),1):
            exec(compile(match["code"],f"{lang}/pipeline/fence-{i}","exec"),module.__dict__,module.__dict__)
    finally:
        sys.modules.pop(module.__name__,None)
    return module

def independent_timeline(program, forwarding):
    # Brute-force issue cycle, then scan backwards for the most recent writer
    # of each register. Test stage-readiness as strict chronological inequalities,
    # rather than using the implementation's derived separation constants.
    issues=[]
    for i,(kind,dest,sources) in enumerate(program):
        cycle=issues[-1]+1 if issues else 0
        while True:
            legal=True
            for reg in sources:
                producer=next((j for j in range(i-1,-1,-1)
                               if program[j][1]==reg),None)
                if producer is None:
                    continue
                producer_cycle=issues[producer]
                producer_kind=program[producer][0]
                if forwarding:
                    availability_stage=2 if producer_kind=="ALU" else 3
                    consuming_stage=2
                else:
                    availability_stage=4
                    consuming_stage=1
                if cycle+consuming_stage <= producer_cycle+availability_stage:
                    legal=False
                    break
            if legal:
                break
            cycle+=1
        issues.append(cycle)
    return tuple(issues)

TABLE={
    0:{False:(False,0),True:(False,1)},
    1:{False:(False,0),True:(False,2)},
    2:{False:(True,1),True:(True,3)},
    3:{False:(True,2),True:(True,3)},
}

class PipelineContractTests(unittest.TestCase):
    def test_exhaustive_short_instruction_schedules(self):
        instruction_forms=[
            ("ALU","a",()),
            ("LOAD","a",()),
            ("ALU","b",("a",)),
            ("LOAD","b",("a",)),
            ("ALU","a",("b",)),
        ]
        for lang in ("en","pt"):
            scheduler=published(lang).issue_cycles
            self.assertEqual(scheduler([],True),())
            for forwarding in (False,True):
                for count in range(5):
                    for program in itertools.product(instruction_forms,repeat=count):
                        with self.subTest(lang=lang,forwarding=forwarding,program=program):
                            actual=scheduler(program,forwarding)
                            expected=independent_timeline(program,forwarding)
                            self.assertEqual(actual,expected)
                            self.assertEqual(
                                published_cycles(actual),
                                0 if not actual else actual[-1]+5,
                            )
            for invalid in (None,1,"yes"):
                with self.assertRaises(ValueError):
                    scheduler([("ALU","a",())],invalid)
            for invalid in (
                [("NOT-ALU","a",())],
                [("ALU","a",("x",),4)],
                [("LOAD","a",["b"])],
                [("ALU","",())],
            ):
                with self.assertRaises(ValueError):scheduler(invalid)

    def test_predictor_exhaustive_short_outcome_traces(self):
        for lang in ("en","pt"):
            Predictor=published(lang).TwoBitPredictor
            for initial in range(4):
                for length in range(8):
                    for outcomes in itertools.product((False,True),repeat=length):
                        oracle_state=initial
                        expected=[]
                        for outcome in outcomes:
                            prediction,next_state=TABLE[oracle_state][outcome]
                            expected.append(prediction)
                            oracle_state=next_state
                        model=Predictor(initial)
                        actual=[model.observe(outcome) for outcome in outcomes]
                        self.assertEqual(actual,expected,(lang,initial,outcomes))
                        self.assertEqual(model.state,oracle_state,(lang,initial,outcomes))
            for invalid in (-1,4,True,1.0):
                with self.assertRaises(ValueError):Predictor(invalid)
            with self.assertRaises(ValueError):Predictor().observe(1)

def published_cycles(issue_times):
    # Separate check for total completion convention including drain.
    return (issue_times[-1]+5) if issue_times else 0

if __name__=="__main__":
    unittest.main()
