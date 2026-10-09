---
id: evidence-based-interviews
title: "Explaining Engineering Decisions with Evidence"
description: "Present technical decisions and past projects using a precise situation-action-result structure, trade-offs and falsifiable impact metrics."
category: communication
difficulty: foundational
updated: 2026-10-09
prerequisites: []
sources:
  - {title: 'MIT CAPD — STAR Method for Behavioral Interviews', url: 'https://capd.mit.edu/resources/the-star-method-for-behavioral-interviews/', kind: university career guidance}
  - {title: 'Google SRE Book — Postmortem Culture', url: 'https://sre.google/sre-book/postmortem-culture/', kind: engineering book}
---
Technical communication is a separate engineering skill: colleagues need to understand what was broken, which constraints mattered, which decisions you actually made and what evidence supports the outcome. A structured explanation is more credible than an unsupported list of technologies. The **STAR** method (Situation, Task, Action, Result) is one way to present a concrete experience [1].

## Separate context, responsibility and outcome
- **Situation:** the business or technical problem, including the scale and observed failure. Avoid unrelated history.
- **Task:** your specific responsibility, constraints and success criterion. Separate team objectives from personal ownership.
- **Action:** the alternatives evaluated, key trade-offs, experiments and implementation you personally contributed.
- **Result:** measured effects, residual risk, what failed, lessons and what remains uncertain.

If an outcome cannot be quantified, report an observable qualitative result and the reason precise measurement was unavailable. Invented metrics undermine the account. If a team delivered a result, distinguish what the team achieved from what you individually designed or implemented [1].

## Worked example: reducing latency
A weak statement is: "I optimized a service using Redis and improved performance." It omits the baseline, workload, causal mechanism and failure cost.

A more rigorous outline:

```text
Situation: p99 read latency exceeded the agreed objective during peak traffic.
Task: reduce tail latency without serving stale authorization decisions.
Action: measured query distribution, added a bounded read cache for public
        metadata only, introduced request coalescing and observed error budgets.
Result: compare baseline and post-change p99 over comparable traffic windows;
        report the exact measured values, trade-offs and any regressions.
```

The example intentionally does not invent numbers. The engineer should be ready to explain the **measurement protocol**: comparable time windows, request mix, confounding releases, sample size and how warm-cache effects were handled.

## Defend architectural trade-offs
Engineering choices have objectives and costs. If selecting a monolith over microsservices, articulate deployment frequency, team boundaries, consistency needs and expected operational overhead. If selecting eventual consistency, explain which user-visible stale reads are acceptable and how they are bounded. If choosing a simpler algorithm over a theoretically faster one, compare realistic input sizes, memory and maintainability.

State decisions as testable propositions, for example: "We expect service p95 under X at Y RPS, measured with workload Z". This is stronger than "The architecture is scalable" because it can be proven wrong and improved.

## Explaining incidents without blame
After an outage, discuss the timeline, triggering conditions, detection gaps, mitigations and follow-up actions without assigning personal fault. Blameless postmortems aim to expose systemic improvements while retaining factual accountability for technical actions [2]. You should not hide your own mistakes: explain what changed in tests, alarms, rollout or documentation so the failure is less likely to recur.

## Exercises and verification
1. Describe a failed migration using the four STAR headings. Include rollback trigger and what was learned.
2. Rewrite "made it 50% faster" as a complete measurement statement: which metric, baseline, sampling window, traffic mix and direction?
3. Pick a technical decision you disagree with. Present the best arguments on both sides before defending your choice.

Precise communication links technical depth to practical ownership. It is not a substitute for engineering evidence; it is the method for making that evidence intelligible.
