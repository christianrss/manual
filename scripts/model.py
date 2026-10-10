from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'content'
LANGS = ('en','pt')
SITE = 'https://manual.christiansoftware.org'

def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding='utf-8'))

def parse_document(path):
    text = Path(path).read_text(encoding='utf-8')
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError(f'Missing YAML frontmatter: {path}')
    front, body = text[4:].split('\n---\n',1)
    data = yaml.safe_load(front)
    return data,body.strip()

def load_modules():
    groups = read_yaml(CONTENT / 'data' / 'modules.yml')
    mapping = {}
    for category, ids in groups.items():
        for ident in ids:
            if ident in mapping:
                raise ValueError(f'Duplicate module assignment: {ident}')
            mapping[ident] = category
    return mapping

def load_articles():
    modules=load_modules()
    articles={}
    for lang in LANGS:
        for path in sorted((CONTENT/lang/'topics').glob('*.md')):
            meta, body = parse_document(path)
            ident = meta['id']
            if ident not in modules:
                raise ValueError(f'Unclassified article: {lang}/{ident}')
            # Compatibility: legacy coarse frontmatter category remains in source.
            # The curated subject-module registry is authoritative for rendering.
            meta['category'] = modules[ident]
            if ident in articles.setdefault(lang,{}):
                raise ValueError(f'Duplicate ID {lang}/{ident}')
            articles[lang][ident]={'meta':meta, 'body':body, 'path':path}
    return articles

def load_tracks():
    return read_yaml(CONTENT/'data'/'curriculum.yml')['tracks']

def load_taxonomy():
    return sorted(read_yaml(CONTENT/'data'/'taxonomy.yml'),key=lambda cat:cat['order'])

def article_url(lang, ident):
    return f'/{lang}/topics/{ident}/'

def track_url(lang,ident):
    return f'/{lang}/tracks/{ident}/'
