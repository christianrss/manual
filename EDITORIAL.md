# Editorial standard

## Reader promise
A reader must be able to derive the idea and reproduce the result. Avoid a glossary dressed up as a chapter. Directness means eliminating repetition, not skipping derivations.

## Required frontmatter
`id, title, description, category, difficulty, updated, prerequisites, sources`.
Sources: ordered list of `{title, url, kind}`; citation numbers are one-based positions in the source list. Prefer official standards and original scholarly sources. Every source cited in text must resolve to a source id. Use `[1]`, `[2]`, etc. ordered to match `sources` list.

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

## Edition 2: depth and reproducibility gate
- The article is **not** done merely because it passes the validator. Every major concept must be defined before use, or linked to a published prerequisite. A reader must be able to reproduce the argument.
- Baseline: at least 700 words of meaningful bilingual content and six technical sections per language. Neither metric is a target or proxy for correctness. More complex areas require separate focused chapters rather than artificial word count inflation.
- Include a proof, invariant or explicit correctness argument for algorithms; include an authority boundary, consistency/failure model, measurable capacity assumptions and operational trade-offs for distributed systems.
- Give at least one worked example with assumptions and intermediate reasoning. Numerical examples must state units and whether values are hypothetical. Avoid claiming certainty from a single benchmark.
- Use counterexamples and failures to show **when** the approach stops being valid. Distinguish worst-case, expected and amortized bounds; do not use `O(1)` unconditionally for hashing or distributed operations.
- Show testable checkpoints, not only rhetorical questions. Executable Python fences (`python` tagged with three backticks or tildes) are executed sequentially per chapter and language in CI. Keep them independently reproducible as a chapter.
- Review both languages for conceptual equivalence, not merely matching metadata. If a chapter grows beyond coherent scope, extract a dedicated topic with explicit prerequisites and stable routes.
- A human technical review of proofs and cited claims is required for 'reference grade'. CI provides only structural and executable checks, not certification of theoretical completeness.

## Priority and article granularity for the SDE II curriculum
A basic topic deserves its own complete article when the reader cannot derive its operations, costs, invariants and failure cases from another existing chapter. In particular, don't skip arrays, list nodes, stacks, queues, tree traversal, sorting, recursion or object design to publish another specialized distributed-systems extension. Include code that runs without an IDE, edge cases and an independent correctness check. System-design chapters must connect requirements, sizing, API/data contracts, failure handling, trade-offs and verification. The hiring organization is referenced only in the dedicated track, not in universal technical chapters.
