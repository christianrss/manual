from __future__ import annotations
import sys, re
from datetime import date
from urllib.parse import urlparse
from pathlib import Path
from model import ROOT, SITE, LANGS, load_articles, load_tracks, load_taxonomy

REQUIRED=('id','title','description','category','difficulty','updated','prerequisites','sources')
ID_RE=re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

def validate():
    errors=[]
    articles=load_articles()
    cats={x['id'] for x in load_taxonomy()}
    eng=set(articles['en']); por=set(articles['pt'])
    if eng!=por: errors.append(f'Unmatched EN/PT IDs: only-en={sorted(eng-por)} only-pt={sorted(por-eng)}')
    for lang in LANGS:
        for ident, entry in articles[lang].items():
            m=entry['meta']; body=entry['body']; p=entry['path']
            for key in REQUIRED:
                if key not in m: errors.append(f'{p}: missing {key}')
            if not ID_RE.fullmatch(ident) or p.stem!=ident: errors.append(f'{p}: invalid id/filename')
            if m.get('category') not in cats: errors.append(f'{p}: unknown category')
            if len(m.get('description',''))<55 or len(m.get('description',''))>170: errors.append(f'{p}: SEO description must be 55..170 chars')
            if len(body.split())<280: errors.append(f'{p}: too short, no shallow filler allowed ({len(body.split())} words)')
            if not re.search(r'^## ',body,re.M): errors.append(f'{p}: missing section headings')
            if not re.search(r'^## (?:Exercises|Exercícios|Verification|Verificação|Checkpoints|Pontos de verificação)',body,re.M|re.I): errors.append(f'{p}: missing exercises/verification section')
            try: date.fromisoformat(str(m.get('updated')))
            except (TypeError,ValueError): errors.append(f'{p}: invalid updated date')
            for pre in m.get('prerequisites',[]):
                if pre not in articles[lang]: errors.append(f'{p}: unknown prerequisite {pre}')
                if pre==ident: errors.append(f'{p}: self-prerequisite')
            sources=m.get('sources',[])
            if not sources: errors.append(f'{p}: needs primary sources')
            for ix,s in enumerate(sources,1):
                if not all(k in s for k in ('title','url','kind')): errors.append(f'{p}: incomplete source {ix}')
                u=urlparse(s.get('url',''))
                if u.scheme!='https' or not u.hostname: errors.append(f'{p}: bad source URL {ix}')
                if f'[{ix}]' not in body: errors.append(f'{p}: source [{ix}] is not cited inline')
            prose = re.sub(r'(?ms)^(```|~~~)[^\n]*\n.*?^\1\s*$', '', body)
            prose = re.sub(r'`[^`\n]*`', '', prose)
            for number in re.findall(r'(?<![A-Za-z0-9_])\[(\d+)\]',prose):
                if int(number)<1 or int(number)>len(sources): errors.append(f'{p}: invalid inline source index [{number}]')
            for img in re.findall(r'!\[[^\]]+\]\(([^)]+)\)',body):
                if img.startswith('/') and not (ROOT/'static'/img.lstrip('/')).is_file():errors.append(f'{p}: missing image {img}')
            for url in re.findall(r'(?<!!)\[[^\]]+\]\((/[^)#]+)(?:#[^)]+)?\)',body):
                bits=url.strip('/').split('/')
                if len(bits)>=3 and bits[1]=='topics' and (bits[0] not in LANGS or bits[2] not in articles[bits[0]]):
                    errors.append(f'{p}: unresolved internal article link {url}')
    def visit(ident,stack,done):
        if ident in stack: errors.append(f'cyclic prerequisites: {" -> ".join(stack+[ident])}'); return
        if ident in done:return
        for pre in articles['en'][ident]['meta'].get('prerequisites',[]):
            if pre in articles['en']: visit(pre,stack+[ident],done)
        done.add(ident)
    done=set()
    for ident in eng: visit(ident,[],done)
    for ident in eng&por:
        a=articles['en'][ident]['meta']; b=articles['pt'][ident]['meta']
        for k in ['category','difficulty','prerequisites']:
            if a.get(k)!=b.get(k):errors.append(f'{ident}: {k} mismatch across translations')
        if [s.get('url') for s in a['sources']] != [s.get('url') for s in b['sources']]:errors.append(f'{ident}: source URL mismatch')
    for tr in load_tracks():
        if not ID_RE.fullmatch(tr['id']):errors.append('Bad track ID')
        for section in tr['sections']:
            if len(section['articles'])!=len(set(section['articles'])):errors.append(f'Track duplicate article in section: {tr["id"]}')
            for ident in section['articles']:
                if ident not in eng&por:errors.append(f'Track {tr["id"]} missing bilingual article {ident}')
        if not tr.get('reference_urls'):errors.append(f'Track {tr["id"]} without references')
    if errors:
        print('VALIDATION FAILED:')
        print('\n'.join(' - '+e for e in errors))
        return False
    print(f'VALIDATED: {len(eng)} paired articles / {len(load_tracks())} learning track(s) / {len(cats)} categories. Offline source URL format checked; external availability NOT checked.')
    return True

if __name__=='__main__':sys.exit(0 if validate() else 1)
