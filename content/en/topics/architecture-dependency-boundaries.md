---
id: architecture-dependency-boundaries
title: "Software architecture: dependency boundaries and modular design"
description: "Derive layered and ports-and-adapters architectures, enforce module dependencies, document decisions and test a modular monolith."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [clean-code-cohesion-coupling, solid-dependency-inversion]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Alistair Cockburn — Hexagonal architecture", url: "https://alistair.cockburn.us/hexagonal-architecture/", kind: "original architecture article"}
  - {title: "Martin Fowler — Monolith First", url: "https://martinfowler.com/bliki/MonolithFirst.html", kind: "original engineering essay"}
---
Software architecture defines **the constraints under which components may change, communicate and fail**. Class structure alone is not architecture: two programs with identical class diagrams can have radically different operational properties when one makes local calls and the other introduces remote boundaries. A useful architectural decision preserves critical invariants, limits the impact of change, and can be verified rather than merely described. Architectural principles distinguish separation of concerns and dependency direction from specific frameworks [1].

## Start from the change and failure requirements

Consider a small order system with pricing, inventory reservation, invoices and an HTTP interface. Assume the first release runs as one deployable application with one transactional database. The business rule is that the payable total must equal the sum of validated line prices, and a confirmed inventory reservation must not exceed available stock. The HTTP framework should not decide prices; the pricing policy should not import the SQL client. These are architectural constraints, not preferences about folder names.

Write down three questions: who owns each invariant, which component has authority to change its data, and what happens when the dependency fails? The order module may coordinate operations but must not modify inventory internals by reaching into its private tables. This still matters inside a monolith: a boundary is a permitted dependency, not necessarily a network hop.

## Compare layered architecture with ports and adapters

A conventional layered architecture divides presentation, application, domain and infrastructure responsibilities. One possible request flow is HTTP controller → application use case → domain policy → repository. The **call direction** describes runtime collaboration; the **source-code dependency direction** determines whether high-level policy can be compiled and tested without framework or persistence code. These directions need not be identical.

In a naïve layered implementation, domain entities instantiate concrete SQL repositories. The controller looks tidy, but the center depends on the edge. Ports and adapters, often called hexagonal architecture, instead define a port as a narrow behavioral contract owned by the application or domain, and an adapter as the implementation at an external boundary [2]. A database adapter implements a persistence port; a web controller is an inbound adapter. This reverses the source dependency without pretending that a database outage disappears.

A port is not automatically an abstract class: a small Python Protocol, function argument or interface can express the required behavior. Avoid creating an adapter for pure arithmetic with no independent change pressure. A boundary should make a real variation, test seam, security rule or deployment concern explicit.

## A modular monolith is a deliberate deployment choice

A modular monolith has independently understandable modules but deploys as one process or unit. It can use local calls and one ACID transaction to maintain selected cross-module invariants, provided the modules coordinate through public application contracts. It cannot guarantee independent deployment or isolate a process crash between modules. Conversely, splitting every module into a service introduces network timeouts, version compatibility, duplicated operational infrastructure, tracing and distributed consistency. Fowler's monolith-first argument is a warning against taking that cost before understanding boundaries [3].

A modular monolith is not a license for arbitrary shared-database writes. If checkout bypasses the inventory API to update inventory rows, the inventory owner can no longer enforce its rules. Even with one database, make ownership and allowed integration points explicit. When extraction becomes justified, moving a local call across a network **changes** its failure semantics: a timeout can leave an ambiguous remote result.

## Make dependency rules executable

The following small checker uses a directed module graph. An edge from module A to module B means A imports B. The permitted set is an architectural policy for a hypothetical application, not a universal prescription. The checker rejects unknown module names and unapproved edges, including a domain layer importing its HTTP adapter.

~~~python
ALLOWED = {
    "http": {"application"},
    "application": {"domain", "ports"},
    "domain": set(),
    "ports": {"domain"},
    "sql_adapter": {"ports", "domain"},
    "bootstrap": {"http", "application", "sql_adapter"},
}

def check_imports(imports):
    for source, targets in imports.items():
        if source not in ALLOWED:
            raise ValueError("unknown source module")
        for target in targets:
            if target not in ALLOWED:
                raise ValueError("unknown target module")
            if target not in ALLOWED[source]:
                raise ValueError("forbidden dependency: " + source + " -> " + target)
    return True

good = {
    "http": {"application"}, "application": {"domain", "ports"},
    "sql_adapter": {"ports"}, "bootstrap": {"sql_adapter", "http"}
}
assert check_imports(good)
for bad in ({"domain": {"http"}}, {"http": {"sql_adapter"}},
            {"application": {"missing"}}):
    try:
        check_imports(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid dependency was accepted")
~~~

For a graph with V declared modules and E supplied import edges, this checker takes O(V + E) time if the input explicitly lists each module once, and O(1) auxiliary memory beyond loop variables and the fixed policy table. With an arbitrary number of modules or a dynamically built policy, storing and checking the policy also has costs. This example enforces *allowed edges*, not cycles within permitted packages, forbidden runtime calls, reflection or dependency inversion correctness. In a real project, an import scanner and CI architecture tests must discover the graph from source files instead of trusting a caller-provided graph.

## Separate structure from the transactional invariant

Suppose checkout reads stock=1, verifies availability, then writes stock=0. Two concurrent requests can both read 1 and confirm. Perfect package boundaries do not prevent this race. A conditional database update, serializable transaction with retry, or an equivalent authoritative reservation protocol must enforce the invariant. The application boundary decides **who may attempt** reservation; the storage and concurrency design decide **whether concurrent attempts are valid**.

Likewise, a fake repository that passes tests establishes only a local contract. It does not prove that the SQL adapter handles deadlocks, duplicate requests, authorization, rollback or retry after timeout. Contract tests across adapters are essential when replacing one implementation with another.

## Record decisions and revisit them with evidence

An architecture decision record (ADR) should identify context, decision, alternatives, consequences and a trigger for reconsideration. For the sample application: choose one modular deployment because cross-module transactions are required and separate scaling has not been measured. Reject premature independent services because they would add network ambiguity. Revisit when profiling shows resource contention, deployment independence becomes an explicit requirement, or ownership boundaries cannot be enforced in one codebase.

Measure change coupling through concrete evidence: which modules must be edited for a new payment provider, which tests must execute, which teams approve a change, and how failures propagate. A diagram saying “low coupling” is not evidence. If every feature edits a common helper and a shared schema, the supposed modularity is weak even if namespaces appear separate.

## Common failure modes and counterexamples

A generic repository interface with dozens of methods can leak table details into domain code; inversion of imports then becomes cosmetic. A “clean” controller can still perform authorization too late. A facade can hide transaction boundaries by silently making several writes. A microservice can have its own database yet remain tightly coupled through synchronous chains that must all succeed. Finally, forbidding every cross-module call may force duplicated business logic. Keep interfaces narrow, but permit the collaboration that real use cases require.

Architecture styles are not maturity rankings. A straightforward layered application may be superior when domain policy is simple and teams benefit from fewer abstractions. Ports and adapters are valuable when stable core rules must be tested against changing infrastructure. Service boundaries are warranted only after their operational and consistency consequences are understood.

## Exercises and verification

1. Add a reporting adapter that reads orders. Decide whether it should import the domain or execute private SQL against another module. Explain the data-ownership consequence.
2. Extend the example with an event publisher. Define a port, then describe how publishing after commit can lose an event and how a transactional outbox changes that failure window.
3. Attempt to add domain → sql_adapter to the import graph. Show the failing test and name which architectural principle it enforces.
4. Design a concurrency test for two reservations of one stock unit. Explain why the import checker cannot establish the required invariant.
5. Write a one-page ADR comparing layered monolith, modular monolith and microservices under stated team size, load and failure assumptions. Identify a measurable trigger that could reverse the decision.

Continue with [SOLID and contracts](/en/topics/solid-dependency-inversion/), [service boundaries](/en/topics/service-boundaries/) and [system-design method](/en/topics/system-design-process/).