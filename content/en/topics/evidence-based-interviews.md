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

## Construct a causal engineering narrative

An account of work should distinguish **observation**, **hypothesis**, **intervention** and **measured outcome**. Suppose latency decreased after a cache rollout. It does not follow automatically that the cache caused all of the improvement: request mix, deployment timing and upstream changes can confound the comparison. Present baseline window, population, measured percentile, sample size, relevant simultaneous changes and remaining uncertainty. Describing the evidence this way conveys judgment rather than memorized interview vocabulary [1].

Use the STAR structure as a communication tool rather than a substitute for engineering facts. 'Situation' establishes constraints and system boundaries; 'Task' separates your responsibility from the team's; 'Action' should include rejected alternatives and the reason; 'Result' should distinguish measured impact from estimated or hoped-for impact. If the outcome is unknown, say so and describe what was observed.

## The design explanation ladder

An effective system design explanation moves through: (1) user-visible requirement; (2) measurable nonfunctional targets; (3) plausible baseline architecture; (4) data ownership and operations; (5) specific bottleneck/failure mode; (6) trade-off and alternative; and (7) validation. For instance, 'use a queue' is a component choice. 'We can accept jobs durably and process them asynchronously because completion within 30 seconds is permitted; duplicate messages are handled by a unique business key' is a defensible contract.

## Challenging your own proposal

Before presenting a solution, try to falsify it. If the design has one database, ask what occurs during an outage. If it uses caches, explain stale reads after writes. If it retries requests, analyze idempotence and retry storms. If it partitions data, explain cross-partition operations and hot keys. If it scales horizontally, name the shared bottleneck. The point is not to make the system infinitely complicated; it is to show that complexity is introduced only for observed or required reasons.

## Behavioral evidence without invented achievements

```text
Context: We observed a recurring failure under condition X.
Ownership: I designed/implemented Y; the team owned Z.
Constraints: We had to preserve invariant I and deliver by date D.
Options: A offered lower latency; B had better failure recovery.
Action: We chose B because invariant I could not tolerate A's trade-off.
Evidence: Tests T1/T2 and metrics M supported the decision.
Outcome: State the observed result, limitations and follow-up.
```

Treat letters as placeholders, never as metrics to invent. For a failed project, discuss detection gaps and corrective actions as seriously as successful delivery. Blameless incident reviews are meant to find systemic weaknesses; they do not eliminate responsibility for factual decisions [2].

## Practice and evaluation rubric

Record a two-minute explanation of one project. Check whether an unfamiliar engineer can identify the problem, the true constraints, your contribution, what you measured and one credible alternative. Then defend a design under a changed requirement: double traffic, one replica lost, strict consistency or half the budget. Finally, explain an incident without blaming individuals and with concrete prevention steps. This evaluation tests structured reasoning rather than perfect English or performative confidence.

## Exercises and verification
1. Describe a failed migration using the four STAR headings. Include rollback trigger and what was learned.
2. Rewrite "made it 50% faster" as a complete measurement statement: which metric, baseline, sampling window, traffic mix and direction?
3. Pick a technical decision you disagree with. Present the best arguments on both sides before defending your choice.

Precise communication links technical depth to practical ownership. It is not a substitute for engineering evidence; it is the method for making that evidence intelligible.
