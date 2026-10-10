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
        self.assertEqual(set(modules.values()) | {'computer-architecture'}, {c['id'] for c in load_taxonomy()})
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
        self.assertTrue(all(load_modules()[x]!='advanced-labs' for x in core))
if __name__=='__main__':unittest.main()
