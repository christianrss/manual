---
name: technical-diagrams
description: Produce precise accessible technical diagrams and verify relationships.
---

1. Establish entities and edge semantics in prose before drawing.
2. Prefer local SVG with viewBox, title, desc and text labels; diagram must be legible on mobile and in print.
3. Explain diagram scope and failure/consistency assumptions in accompanying text.
4. If using Mermaid, commit `.mmd` source and treat JS renderer as progressive enhancement, never as sole source of an essential definition.
5. Avoid screenshots and decorative diagrams. Validate labels against the written architecture.
