# Diagram sources

The project mark, architecture, deployment workflow and wiring diagrams are deterministic SVGs
built by [render_diagrams.py](../../scripts/render_diagrams.py), using only the
Python standard library. The SVGs also remain directly editable in vector tools.

```bash
make diagrams
make diagrams-check
```

Outputs: [project mark](../images/project-mark.svg), [architecture](../images/architecture.svg),
[model workflow](../images/model-workflow.svg), [wiring](../images/wiring.svg).

Review diagrams at normal README width and check label placement, arrow
direction and contrast. GPIO labels must agree with the firmware headers.

The project mark is a symbolic seven-chip illustration, not a wiring reference.
Use the wiring diagram for actual connections.
