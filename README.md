# Engineering Manual

Source for `https://manual.christiansoftware.org/`. An English/Portuguese, old-school technical reference with modern static architecture, full-text search, article outline, diagrams, sources and learning paths.

## Local build

```bash
python -m pip install -r requirements.txt
python scripts/validate.py
python scripts/build.py
python -m unittest discover -s tests -v
python -m http.server 8000 --directory dist
```

Open `http://localhost:8000/`. Index at `/en/` and `/pt/`.

## Edit
- Topics: `content/en/topics/*.md` and `content/pt/topics/*.md`; paired semantic IDs.
- Categories: `content/data/taxonomy.yml`.
- Tracks: `content/data/curriculum.yml` referencing existing topic IDs.
- Global look: `styles/manual.css`.
- Agent governance: `AGENTS.md`, `EDITORIAL.md`, `.agents/skills/**/SKILL.md`.
- HTML rendering: `scripts/build.py`, `templates/`.
- Art: `static/diagrams/`.

## Hosting
GitHub Pages through `.github/workflows/pages.yml`. Set Pages source to GitHub Actions. Configure `manual.christiansoftware.org` as custom domain and DNS CNAME `manual -> <user>.github.io` if using GitHub Pages. DNS record changes happen at your DNS provider and are **not** performed by the repository build.

## Security and privacy
No analytics, no account, no cookies. Track progress is only browser `localStorage`. Browser-side search does not send queries anywhere.

## Scope
Initial chapters are the foundation, not a claim to a complete interview syllabus. The named interview path includes disclosed coverage gaps. This site is independently produced and unaffiliated with employers.
