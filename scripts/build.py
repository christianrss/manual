from __future__ import annotations
import html, json, re, shutil, sys
from pathlib import Path
from datetime import date
from urllib.parse import quote
from html.parser import HTMLParser
import mistune
from jinja2 import Environment, FileSystemLoader, select_autoescape
from model import ROOT, SITE, LANGS, load_articles, load_taxonomy, load_tracks, article_url, track_url
from validate import validate

OUT=ROOT/'dist'
I18N={
'en':{'site':'Engineering Manual','tagline':'An open reference for computer science and software engineering.','topics':'Topics','tracks':'Study tracks','index':'Index','onthispage':'On this page','sources':'Sources','prerequisites':'Prerequisites','related':'Related reading','alltopics':'All chapters','browse':'Browse by category','updated':'Reviewed','difficulty':'Level','search':'Search the manual','search_hint':'Search chapters, diagrams and concepts','results':'Search results','none':'No matching articles.','next':'Next','previous':'Previous','read':'Read chapter','open':'Open track','progress':'Track progress','clear':'Reset progress','note':'Progress is stored only in this browser.','intro':'Theory, reasoning, worked examples and verifiable references.','unaffiliated':'Independent educational material; not endorsed by the named companies.','coverage':'Not yet covered in this edition','references':'Publicly documented requirements','homepage':'Home','skip':'Skip to content','theme':'Language'},
'pt':{'site':'Manual de Engenharia','tagline':'Uma referência aberta de Ciência da Computação e Engenharia de Software.','topics':'Capítulos','tracks':'Trilhas de estudo','index':'Índice','onthispage':'Nesta página','sources':'Referências','prerequisites':'Pré-requisitos','related':'Leituras relacionadas','alltopics':'Todos os capítulos','browse':'Navegar por categoria','updated':'Revisado','difficulty':'Nível','search':'Buscar no manual','search_hint':'Pesquisar capítulos, diagramas e conceitos','results':'Resultados da busca','none':'Nenhum capítulo encontrado.','next':'Próximo','previous':'Anterior','read':'Ler capítulo','open':'Abrir trilha','progress':'Progresso da trilha','clear':'Limpar progresso','note':'O progresso fica armazenado somente neste navegador.','intro':'Teoria, raciocínio, exemplos completos e fontes verificáveis.','unaffiliated':'Material educacional independente, sem endosso das empresas citadas.','coverage':'Ainda não publicado nesta edição','references':'Requisitos documentados publicamente','homepage':'Início','skip':'Ir ao conteúdo','theme':'Idioma'}}

def slug(s):
    import unicodedata
    s=unicodedata.normalize('NFKD', s)
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-') or 'section'

class Renderer(mistune.HTMLRenderer):
    def __init__(self):
        super().__init__(escape=True)
        self.headings=[]
        self.counts={}
    def heading(self,text,level,**attrs):
        label=re.sub(r'<[^>]+>','',text)
        base=slug(html.unescape(label))
        i=self.counts.get(base,0); self.counts[base]=i+1
        ident=base if not i else f'{base}-{i+1}'
        if level in (2,3):self.headings.append({'level':level,'title':html.unescape(label),'id':ident})
        return f'<h{level} id="{ident}">{text}<a class="anchor" href="#{ident}" aria-label="Section link">#</a></h{level}>\n'
    def text(self,text):
        esc=html.escape(text)
        return re.sub(r'\[(\d+)\]',lambda m: f'<a class="citation" href="#source-{m.group(1)}" aria-label="Reference {m.group(1)}">[{m.group(1)}]</a>',esc)
    def block_code(self,code,info=None):
        language=(info or '').strip().split(' ')[0]
        if language=='mermaid': return '<pre class="mermaid">'+html.escape(code)+'</pre>\n'
        return f'<pre class="code"><code class="language-{html.escape(language)}">{html.escape(code)}</code></pre>\n'
    def link(self,text,url,title=None):
        url=html.escape(url,quote=True)
        attr=' rel="noopener noreferrer"' if url.startswith('https://') else ''
        ttl=f' title="{html.escape(title,quote=True)}"' if title else ''
        return f'<a href="{url}"{attr}{ttl}>{text}</a>'
    def image(self,text,url,title=None):
        return f'<figure><img loading="lazy" src="{html.escape(url,quote=True)}" alt="{html.escape(re.sub("<[^>]+>","",text),quote=True)}"><figcaption>{text}</figcaption></figure>\n'

def render_markdown(md):
    r=Renderer()
    parser=mistune.create_markdown(renderer=r,plugins=['table','strikethrough','url','task_lists'])
    body=parser(md)
    return body,r.headings

def write(rel,content):
    p=OUT/rel.lstrip('/'); p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8')

def meta_context(lang,kind,title,description,path,updated=None,other_path=None):
    return {'lang':lang,'tr':I18N[lang],'kind':kind,'page_title':title,'description':description,'path':path,'canonical':SITE+path,'alternate':SITE+(other_path or path.replace(f'/{lang}/',f'/{{other}}/')),'updated':str(updated or date.today()),'year':date.today().year}

def build():
    if not validate():return 1
    if OUT.exists():shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(ROOT/'static',OUT,dirs_exist_ok=True)
    shutil.copy2(ROOT/'styles'/'manual.css',OUT/'manual.css')
    shutil.copy2(ROOT/'src'/'search.js',OUT/'search.js')
    shutil.copy2(ROOT/'src'/'progress.js',OUT/'progress.js')
    env=Environment(loader=FileSystemLoader(ROOT/'templates'),autoescape=select_autoescape(['html','xml']))
    templates={k:env.get_template(k+'.html') for k in ['base','home','article','track','track-index','search']}
    arts=load_articles(); cats=load_taxonomy(); tracks=load_tracks()
    cat_map={x['id']:x for x in cats}
    # stable category grouping and backlinks
    refs={k:[] for k in arts['en']}
    for ident,obj in arts['en'].items():
        for pre in obj['meta']['prerequisites']:refs[pre].append(ident)
    pages=[]; idx=[]
    sitemap=[]
    for lang in LANGS:
        catalog={key:dict(value['meta'],url=article_url(lang,key)) for key,value in arts[lang].items()}
        organized=[dict(category=c,items=sorted([m for m in catalog.values() if m['category']==c['id']],key=lambda m:m['title'].lower())) for c in cats]
        sidebar=[dict(label=x['category']['title'][lang],items=x['items']) for x in organized if x['items']]
        shared={'categories':organized,'sidebar':sidebar,'tracks':tracks,'catalog':catalog,'lang':lang,'tr':I18N[lang]}
        path=f'/{lang}/'
        ctx=meta_context(lang,'CollectionPage',I18N[lang]['site'],I18N[lang]['tagline'],path,other_path=f'/{"pt" if lang=="en" else "en"}/')
        write(path+'index.html',templates['home'].render(**{**shared,**ctx}))
        sitemap.append((path,path.replace(f'/{lang}/',f'/{"pt" if lang=="en" else "en"}/')))
        path=f'/{lang}/search/'
        ctx=meta_context(lang,'SearchResultsPage',I18N[lang]['search'],I18N[lang]['search_hint'],path,other_path=f'/{"pt" if lang=="en" else "en"}/search/')
        write(path+'index.html',templates['search'].render(**{**shared,**ctx}))
        for ident, entry in arts[lang].items():
            m=entry['meta']; body,heading=render_markdown(entry['body']); path=article_url(lang,ident)
            ctx=meta_context(lang,'TechArticle',m['title'],m['description'],path,m['updated'],article_url('pt' if lang=='en' else 'en',ident))
            curr=dict(m,html=body,toc=heading,prereq=[catalog[x] for x in m['prerequisites']],backlinks=[catalog[x] for x in refs[ident]])
            write(path+'index.html',templates['article'].render(**{**shared,**ctx,'article':curr,'category':cat_map[m['category']]}))
            sitemap.append((path,article_url('pt' if lang=='en' else 'en',ident)))
            from bs4 import BeautifulSoup
            plain=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
            idx.append({'lang':lang,'url':path,'title':m['title'],'description':m['description'],'category':cat_map[m['category']]['title'][lang],'text':plain[:17000]})
        path=f'/{lang}/tracks/'
        ctx=meta_context(lang,'CollectionPage',I18N[lang]['tracks'],I18N[lang]['intro'],path,other_path=f'/{"pt" if lang=="en" else "en"}/tracks/')
        write(path+'index.html',templates['track-index'].render(**{**shared,**ctx}))
        sitemap.append((path,f'/{"pt" if lang=="en" else "en"}/tracks/'))
        for track in tracks:
            path=track_url(lang,track['id'])
            ctx=meta_context(lang,'LearningResource',track['title'][lang],track['description'][lang],path,other_path=track_url('pt' if lang=='en' else 'en',track['id']))
            sections=[{'title':sec['title'][lang], 'articles':[catalog[ident] for ident in sec['articles']]} for sec in track['sections']]
            write(path+'index.html',templates['track'].render(**{**shared,**ctx,'track':track,'sections':sections,'planned':track['planned_topics'][lang]}))
            sitemap.append((path,track_url('pt' if lang=='en' else 'en',track['id'])))
    write('search-index.json',json.dumps(idx,ensure_ascii=False,separators=(',',':')))
    write('robots.txt','User-agent: *\nAllow: /\nSitemap: '+SITE+'/sitemap.xml\n')
    write('llms.txt','# Engineering Manual\n\n> Independent bilingual technical reference, canonical public chapters and interview study paths.\n\n## English\n- '+SITE+'/en/\n- '+SITE+'/en/tracks/\n\n## Português\n- '+SITE+'/pt/\n- '+SITE+'/pt/tracks/\n\n## Citation\nPlease attribute original explanations to Engineering Manual and follow per-chapter reference lists.\n')
    write('CNAME','manual.christiansoftware.org\n')
    entries=[]
    for path,alternate in sorted(set(sitemap)):
        entries.append(f'<url><loc>{SITE}{path}</loc><xhtml:link rel="alternate" hreflang="{path.split("/")[1]}" href="{SITE}{path}"/><xhtml:link rel="alternate" hreflang="{alternate.split("/")[1]}" href="{SITE}{alternate}"/></url>')
    write('sitemap.xml','<?xml version="1.0" encoding="utf-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'+'\n'.join(entries)+'\n</urlset>')
    write('index.html','''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Engineering Manual / Manual de Engenharia</title><meta name="description" content="An open bilingual reference for computer science and software engineering."><link rel="canonical" href="https://manual.christiansoftware.org/"><link rel="alternate" hreflang="en" href="https://manual.christiansoftware.org/en/"><link rel="alternate" hreflang="pt-BR" href="https://manual.christiansoftware.org/pt/"><link rel="stylesheet" href="/manual.css"></head><body><main class="language-gateway"><p class="overline">CHRISTIAN SOFTWARE / ENGINEERING MANUAL</p><h1>Engineering Manual</h1><p>An open reference to computer science and software engineering.</p><ul><li><a href="/en/" lang="en">Read in English →</a></li><li><a href="/pt/" lang="pt-BR">Ler em português →</a></li></ul></main></body></html>''')
    print(f'BUILT: {len(sitemap)+1} HTML pages, {len(idx)} search records, assets, sitemap and CNAME in {OUT}')
    return 0

if __name__=='__main__':sys.exit(build())
