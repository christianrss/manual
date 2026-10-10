import sys,unittest,json,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import ROOT,load_articles,load_tracks
from validate import validate
from bs4 import BeautifulSoup

class SiteTests(unittest.TestCase):
 def test_content_valid(self):self.assertTrue(validate())
 def test_every_pair_built(self):
  a=load_articles()
  for lang in ['en','pt']:
   for ident in a[lang]:
    p=ROOT/'dist'/lang/'topics'/ident/'index.html'
    self.assertTrue(p.is_file(),str(p))
    s=BeautifulSoup(p.read_text(encoding='utf-8'),'html.parser')
    self.assertEqual(s.html['lang'],'pt-BR' if lang=='pt' else 'en')
    self.assertEqual(len(s.select('link[rel="canonical"]')),1)
    self.assertTrue(s.find('h1'))
    self.assertEqual(len(s.select('li[id^="source-"]')),len(a[lang][ident]['meta']['sources']))
 def test_search_index(self):
  data=json.loads((ROOT/'dist'/'search-index.json').read_text(encoding='utf-8'))
  self.assertEqual(len(data),sum(map(len,load_articles().values())))
  self.assertTrue(all(x['text'] and x['url'].startswith('/'+x['lang']+'/topics/') for x in data))
 def test_tracks(self):
  for lang in ['en','pt']:
   for track in load_tracks():
    p=ROOT/'dist'/lang/'tracks'/track['id']/'index.html'
    s=BeautifulSoup(p.read_text(encoding='utf-8'),'html.parser')
    self.assertEqual(len(s.select('input[data-topic]')),sum(len(x['articles']) for x in track['sections']))
    self.assertTrue(s.select_one('#progress-label'))
    self.assertNotIn('built-in method',s.get_text())
    self.assertTrue(s.select_one('#progress-reset'))
 def test_seo(self):
  html=(ROOT/'dist'/'en'/'topics'/'caching'/'index.html').read_text(encoding='utf-8')
  for text in ['hreflang="pt-BR"','application/ld+json','rel="canonical"','id="references"']:
   self.assertIn(text,html)
  self.assertTrue((ROOT/'dist'/'CNAME').is_file())
  self.assertIn('sitemap.xml',(ROOT/'dist'/'robots.txt').read_text())
 def test_author_signature_in_both_languages(self):
  for lang, label, role, education in [
   ('en','Authored and edited by','Data Science Technologist','Postgraduate Degree in Electronic Engineering and Robotics'),
   ('pt','Autoria e edição técnica','Tecnólogo em Ciência de Dados','Pós-graduado em Engenharia Eletrônica e Robótica'),
  ]:
   with self.subTest(lang=lang):
    s=BeautifulSoup((ROOT/'dist'/lang/'index.html').read_text(encoding='utf-8'),'html.parser')
    signature=s.select_one('footer.site-footer .author-signature')
    self.assertIsNotNone(signature)
    self.assertEqual(signature.select_one('.author-signature-name').get_text(strip=True),'Christian Rafael de Souza Silva')
    self.assertEqual(signature.select_one('.author-signature-label').get_text(strip=True),label)
    self.assertIn(role,signature.select_one('.author-signature-role').get_text())
    self.assertIn(education,signature.select_one('.author-signature-education').get_text())
    image=signature.select_one('img')
    self.assertEqual(image.get('src'),'https://me.christiansoftware.org/assets/christian-rafael-photo.jpg')
    self.assertEqual(image.get('width'),'46')
    self.assertIsNotNone(s.select_one('footer.site-footer .site-footer-meta'))
 def test_analytics_on_all_generated_pages(self):
  pages=list((ROOT/'dist').rglob('*.html'))
  self.assertGreaterEqual(len(pages), 45)
  for page in pages:
   with self.subTest(page=str(page.relative_to(ROOT/'dist'))):
    html=page.read_text(encoding='utf-8')
    soup=BeautifulSoup(html,'html.parser')
    gtag_scripts=soup.find_all('script',src='https://www.googletagmanager.com/gtag/js?id=G-J3Y670EV88')
    self.assertEqual(len(gtag_scripts),1)
    self.assertTrue(gtag_scripts[0].has_attr('async'))
    self.assertEqual(html.count("gtag('config', 'G-J3Y670EV88')"),1)
    self.assertIn('window.dataLayer = window.dataLayer || []',html)

if __name__=='__main__':unittest.main()
