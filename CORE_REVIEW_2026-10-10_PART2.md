# Core quality review: contracts, patterns, testing, practice (2026-10-10)

Second targeted editorial pass following `CORE_REVIEW_2026-10-10.md`. Scope: **four paired EN/PT chapters**; no additional articles, no renamed IDs, no changed routes.

| Chapter | Specific audit finding | Correction and reproducible evidence |
| --- | --- | --- |
| Arrays and strings | The purported ASCII-only filter checked `char.lower()`, admitting non-ASCII U+0130 or U+212A through Unicode case conversion | Check the **original** code point in ASCII ranges; encode ASCII case mapping explicitly; add Unicode counterexamples and independent regression tests |
| Refactoring and patterns | Strategy and Adapter had code, but Decorator was only described; comparison between old/new policies could share the same rounding defect | Add functioning logging Decorator preserving the wrapped method, test failure semantics, and test independent cent-rounding cases |
| Testing strategies | The billed-total example insufficiently specified its numeric domain and could treat `bool` as `int`; nonfinite Decimal inputs were not explicitly rejected | Require finite Decimal values and an exact positive integer quantity; add explicit NaN/Infinity/type and upper-bound tests |
| Algorithm interview workshop | Fully worked examples could be mistaken for unseen evaluation | Separate learning from blind simulation; add timebox, independent unfamiliar assessment guidance and evidence limits |

Technical status: revised and regression-tested in Python by the repository's chapter fence runner and dedicated new unit tests. These checks are finite examples, not universal proofs or independent human peer review. Keep the complete Archive track, with P0 DSA/OOP/quality before optional infrastructure. Next candidates: deeper array/graph techniques, coverage of Clean Code and broader design patterns, language runtime and networking foundations.

Amazon primary references: [SDE II online assessment](https://amazon.jobs/content/en/how-we-hire/sde-ii-oa-prep) and [SDE II interview](https://amazon.jobs/content/pt/how-we-hire/sde-ii-interview-prep).
