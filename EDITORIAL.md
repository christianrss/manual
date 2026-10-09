# Editorial standard

## Reader promise
A reader must be able to derive the idea and reproduce the result. Avoid a glossary dressed up as a chapter. Directness means eliminating repetition, not skipping derivations.

## Required frontmatter
`id, title, description, category, difficulty, updated, prerequisites, sources`.
Sources: list of `{id, title, url, kind}`. Prefer official standards and original scholarly sources. Every source cited in text must resolve to a source id. Use `[1]`, `[2]`, etc. ordered to match `sources` list.

## Chapter spine
1. What problem and when it arises.
2. Exact definitions, assumptions and notation.
3. Reasoning, invariant, proof or conceptual derivation.
4. Worked example and/or small algorithm or architecture.
5. Complexity, costs, consistency and failure modes.
6. Conditions when the technique is wrong or unsuitable.
7. Checkpoints with worked answers or verifiable tests.
8. Explicit source list (auto-rendered from metadata).

## Quality gate
- No unspecified variables in formulas.
- If claiming O(n), state the input size and assumptions.
- If claiming distributed guarantees, name consistency/failure model.
- If showing code, state input contract and edge cases; include runnable tests when feasible.
- Internal links resolve; alt text for graphics; tables have headings.
- EN/PT articles must preserve scope, definitions and warnings.
- A track may declare planned topics; never represent them as published.
- Disclose that tracks are independently curated, not endorsed by employers.
