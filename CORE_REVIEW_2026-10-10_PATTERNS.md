# Pattern families: focused technical review — 2026-10-10

Scope: one new bilingual chapter, integrated in the Amazon SDE II and Computer Science core tracks; no comprehensive review of 88 existing pairs.

- Builder: steps, strict heading validation, duplicate prevention, snapshot immutability and bounded complexity.
- Facade: combine read-only catalog and stock while distinguishing missing-product and incomplete-stock errors; no guarantee of transactional consistency.
- Observer: synchronous subscription, deterministic order, snapshot-on-publish, mutation during callbacks and fail-fast exception propagation; no claims of message durability.
- Alternative designs and counterexamples, differentiating factories, State, Strategy, Mediator and Command.
- Independent Python regression tests in `tests/test_pattern_family_contracts.py`, plus prerequisites and track-order assertions.

Sources: [pattern catalog](https://refactoring.guru/design-patterns/catalog), [Builder](https://refactoring.guru/design-patterns/builder), [Facade](https://refactoring.guru/design-patterns/facade), and [Observer](https://refactoring.guru/design-patterns/observer). CI verifies limited cases, not independent academic peer review, thread safety, production delivery or interview readiness.
