# Diagram sources

The architecture, deployment workflow and wiring diagrams are deterministic SVGs
built by [render_diagrams.py](../../scripts/render_diagrams.py), using only the
Python standard library. The SVGs also remain directly editable in vector tools.

```bash
python scripts/render_diagrams.py
python scripts/render_diagrams.py --check
```

Outputs: [architecture](../images/architecture.svg),
[model workflow](../images/model-workflow.svg), [wiring](../images/wiring.svg).

Review diagrams at normal README width and check label placement, arrow
direction and contrast. GPIO labels must agree with the firmware headers.
