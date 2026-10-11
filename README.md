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
Google Analytics 4 (`G-J3Y670EV88`) is installed on all generated HTML pages, including the root language gateway, via the shared template and static root page. It loads `gtag.js` from Google and may use cookies and collect usage information under Google's policies. No user account is required. Track progress is stored only in browser `localStorage`; browser-side search does not submit queries to this site's servers. Review privacy and consent obligations for your audience before relying on analytics data.

## Analytics

The Google tag is managed in `templates/base.html` (all localized documentation, search and track pages) and the generated root page in `scripts/build.py`. Its measurement ID is `G-J3Y670EV88`. Edit both integration points if the ID changes; `tests/test_static.py` enforces their presence exactly once in every generated HTML page. Google Analytics data is viewed in the GA4 property, not in the GitHub repository. See [Google's privacy information](https://policies.google.com/technologies/partner-sites) for third-party data processing details.

## Scope
Initial chapters are the foundation, not a claim to a complete interview syllabus. The named interview path includes disclosed coverage gaps. This site is independently produced and unaffiliated with employers.

## Curriculum governance

[CURRICULUM.md](CURRICULUM.md) is the editorial contract: prerequisite graph, quality gates, Amazon SDE II priority and explicit unpublished foundations. `content/data/modules.yml` classifies chapters. Track separation preserves the full technical archive while preventing specialized infrastructure labs from substituting for core CS material.

## Original independent practice assessments

The repository includes three public, unsolved Python assessments. For assessment III, implement the functions in `examples/python/unsolved_drills_3.py` and run `python examples/python/drill_grader_3.py`. The fixtures are publicly visible; they are not hidden tests or reference implementations. Assessment III combines dynamic programming and idempotent state-transition contracts; it does not implement persistent transactions or distributed exactly-once delivery.

Assessment IV adds a **synthetic, intentionally defective** ticket query in `examples/python/legacy_ticket_search.py`, an unsolved corrected contract in `examples/python/refactor_ticket_search.py`, and `python examples/python/ticket_search_grader.py`. The legacy implementation is for characterization only: do not deploy or copy it for authorization. The sample requires server-side authenticated tenant identity outside its in-memory function.

## Independent system-design review: usage metering

The original bilingual `usage-metering-system-design-assessment` provides a hypothetical usage-based billing brief with delayed events, replay, invoice corrections and tenant isolation. Its public [scenario](examples/system-design/usage_metering_scenario.json), [submission rubric](examples/system-design/usage_metering_submission_template.md) and [arithmetic model](examples/python/usage_metering_design_math.py) support reproducible **quantitative checks only**. Architecture answers require human review; nothing here runs a live billing or event-processing service.

## Parsing and formal-language exercises

The paired chapter `context-free-grammars-parsing` follows finite automata and is supported by `examples/python/context_free_parser.py`: a stack recognizer for nested brackets, a recursive syntax-tree parser and an Earley-style fixed-point CFG membership recognizer. `tests/test_context_free_grammars_parsing_contracts.py` checks these against independent finite oracles. The chart algorithm is intentionally educational and does not provide optimized cubic Earley performance, a full compiler, token diagnostics or a packed parse forest.
