---
name: release-qa
description: Gate content, i18n, navigation, search, static HTML, SEO and GitHub Pages deploy.
---

1. Run `python scripts/validate.py` then `python scripts/build.py` then `python -m unittest discover -s tests -v`.
2. Check the emitted `dist/` pages and `search-index.json` against article counts and languages.
3. Verify canonical/hreflang, robots, sitemap, lang, empty-page checks and broken internal links.
4. Inspect 375px/768px/desktop layouts with a browser, keyboard search and mobile menu.
5. Verify external sources manually when online; CI only checks URL format, not reachability.
6. After deployment confirm actual HTTP availability, TLS and DNS; if unavailable say so.
