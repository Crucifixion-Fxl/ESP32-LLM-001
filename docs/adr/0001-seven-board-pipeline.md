# ADR 0001: Use a seven-board inference pipeline

Status: documented existing design

## Context

The supported Qwen2-0.5B configuration has 24 transformer layers. Each ESP32-S3
N16R8 board has 16 MB flash and 8 MB PSRAM. Model weights and working state must
be distributed across multiple boards.

## Decision

Keep one master for tokenization, INT4 embeddings, final normalization, the LM
head and sampling. Assign four consecutive layers to each of six compute nodes.
Send float32 hidden states through the nodes over SPI and return the last result
to the master. Weights remain local to each board.

This record describes the existing upstream-derived architecture; it does not
claim a new topology or a comparison against unmeasured alternatives.

## Consequences

- One node firmware image serves all six nodes; the layer artifact identifies each node's workload.
- Physical node order and layer-file order must agree.
- Every token depends on every node and the return link; a broken hop blocks the pipeline.
- Serial execution distributes memory use but does not provide concurrent request throughput.
- Changes to model dimensions require changes across firmware and export tools.

See [architecture and wiring](../architecture.md) and the
[project specification](../product-spec.md).
