# Architecture Decision Record: Manual v1

- **Public URL:** https://manual.christiansoftware.org/
- **Model:** Git-first, statically generated, deployable to GitHub Pages; Python builder with pinned dependencies, Markdown content, YAML track manifest, Jinja templates. No persistent backend.
- **Purpose:** A durable, well-sourced computer science and software engineering reference. Tracks are separate projections of published chapters.
- **Bilingual routing:** `/en/`, `/pt/`; one semantic ID per EN/PT pair, stable URLs, `hreflang` and canonical tags.
- **Search:** browser-side, deterministic build-time JSON index; no remote search service, full text and category filter.
- **Information architecture:** taxonomic category sidebar; per-page heading TOC; breadcrumbs; related prerequisites; backlinks; course index; explicit track progress via localStorage.
- **Diagrams:** committed local SVG preferred for essential figures, source included; fenced `mermaid` as optional enhancement only, with code fallback. No externally hosted images required.
- **SEO:** prerendered HTML, robots, sitemap, canonical, hreflang, Article or CollectionPage JSON-LD, descriptive titles and descriptions, internal links and source references, llms.txt.
- **Performance and accessibility:** low JS, responsive CSS, keyboard-navigation, semantic headings, no proprietary fonts, WCAG-conscious contrast, reduced motion.
- **Safety:** generator escapes article content except author-controlled safe Markdown; no user content is submitted to the application backend. The site integrates Google Analytics 4 (`G-J3Y670EV88`) as a third-party pageview analytics service; local study progress remains in the browser. Visitor privacy, external processing and consent requirements must be considered.
- **Design system:** old-school academic/Unix manuals, white background, blue/purple anchors, monochrome rules, compact tables, restrained monospace metadata; modern HTML/CSS internals.
- **Deployment:** GitHub Actions validation and Pages publishing; custom domain CNAME needs DNS configuration and repository settings.
- **Constraint:** builder favors reproducible minimal dependencies over a large front-end framework. If future exercise sandbox needs isolated compilation, build it as a separate application/API, not inside the static manual.
