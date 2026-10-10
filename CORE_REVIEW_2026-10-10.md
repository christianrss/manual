# Focused core technical review — 2026-10-10

This is a substantive, limited editorial review of five bilingual chapter pairs, not a claim of full peer-reviewed coverage.

| Chapter | Corrective action | Verification boundary |
| --- | --- | --- |
| `complexity-analysis` | Replaced repeated analysis with a distinct nested-log counting example | RAM model and executable assertions, not Python bigint timing guarantees |
| `binary-search` | Replaced generic capacity discussion with proved monotone search and test cases | Positivity, contiguity, greedy feasibility, arithmetic assumptions |
| `solid-dependency-inversion` | Made behavioral substitution concrete with a deliberately invalid sender | Local dispatch cardinality only, not network delivery |
| `low-level-design` | Executable coverage for every local state/event pair | No DB crash/concurrency claims |
| `system-design-process` | Added quantified saturation, queue growth and recovery exercise | Hypothetical constant-rate fluid model only |

Every EN/PT change preserves its stable article ID and references. Fences run as part of the existing chapter-execution tests. A passing build does not constitute independent expert review. Next editorial targets remain patterns/refactoring, arrays and strings, testing, DSA problem-solving, interview exercises, and eventually architectural fundamentals, security and networks.

The [Amazon SDE II OA](https://amazon.jobs/content/en/how-we-hire/sde-ii-oa-prep) calls for syntactically correct implementation, data structures/algorithms and maintainable code. The [interview guide](https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep) also includes system design and behavioral evidence. Prioritize those, without conflating the OA and the later interview loop.
