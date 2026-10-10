import unittest, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from model import load_articles, load_tracks, load_taxonomy, load_modules
class CurriculumIntegrityTests(unittest.TestCase):
    def test_every_article_classified_once(self):
        modules=load_modules()
        a=load_articles()
        self.assertEqual(set(modules),set(a['en']))
        self.assertEqual(set(a['en']),set(a['pt']))
        self.assertEqual(set(modules.values()), {c['id'] for c in load_taxonomy()})
    def test_interview_track_is_fundamental(self):
        tracks=load_tracks()
        self.assertEqual([t['id'] for t in tracks],['amazon-sde-ii','computer-science-core','specialized-systems-labs'])
        for track in tracks:
            ids=[x for sec in track['sections'] for x in sec['articles']]
            self.assertEqual(len(ids),len(set(ids)),track['id'])
            self.assertTrue(set(ids)<=set(load_articles()['en']))
        core=[x for s in tracks[0]['sections'] for x in s['articles']]
        labs=[x for s in tracks[2]['sections'] for x in s['articles']]
        self.assertFalse(set(core)&set(labs))
        self.assertLess(core.index('complexity-analysis'),core.index('system-design-process'))
        self.assertLess(core.index('object-oriented-design'),core.index('system-design-process'))
        self.assertLess(core.index('machine-representation-isa-cache'),core.index('processes-virtual-memory'))
        self.assertEqual(load_modules()['machine-representation-isa-cache'],'computer-architecture')
        self.assertTrue(all(load_modules()[x]!='advanced-labs' for x in core))
        # Targeted prerequisite audit of the foundational software-design block.
        self.assertLess(core.index('testing-maintainability'), core.index('clean-code-cohesion-coupling'))
        self.assertLess(core.index('clean-code-cohesion-coupling'), core.index('object-oriented-design'))
        self.assertLess(core.index('object-oriented-design'), core.index('low-level-design'))
        self.assertLess(core.index('low-level-design'), core.index('solid-dependency-inversion'))
        self.assertLess(core.index('testing-strategies'), core.index('refactoring-design-patterns'))
        self.assertLess(core.index('refactoring-design-patterns'), core.index('design-pattern-families'))
        self.assertLess(core.index('rate-limiting'), core.index('maintainable-implementation-workshop'))
        self.assertLess(core.index('capacity-estimation'), core.index('system-design-process'))
        for article in ['clean-code-cohesion-coupling', 'object-oriented-design', 'low-level-design', 'solid-dependency-inversion', 'testing-strategies', 'refactoring-design-patterns', 'design-pattern-families']:
            for prereq in load_articles()['en'][article]['meta']['prerequisites']:
                self.assertLess(core.index(prereq), core.index(article), f'{prereq} must precede {article}')
    def test_cs_core_pattern_and_capacity_order(self):
        cs=[ident for section in load_tracks()[1]['sections'] for ident in section['articles']]
        self.assertLess(cs.index('refactoring-design-patterns'), cs.index('design-pattern-families'))
        self.assertLess(cs.index('capacity-estimation'), cs.index('system-design-process'))
        self.assertLess(cs.index('machine-representation-isa-cache'),cs.index('processes-virtual-memory'))
if __name__=='__main__':unittest.main()
