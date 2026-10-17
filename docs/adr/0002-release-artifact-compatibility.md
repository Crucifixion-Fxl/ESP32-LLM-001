# ADR 0002: Preserve release artifacts while organizing source by responsibility

Status: accepted

## Context

Existing users can have v1.0.0 firmware, packed model files, downloaded base
weights and training checkpoints. Renaming source files must not force them to
redownload models or silently reinterpret a binary.

## Decision

Group firmware by board role and Python modules by workflow stage. Keep ESP-IDF's
`main/` component convention, and invoke Python modules from the repository root.
Expose common development commands through the root `Makefile`.

Preserve `master_board.bin`, `node_board.bin`, model binary filenames, partition
offsets and packed formats. Keep `Qwen2-0.5B/` and `cropped_Qwen/` as default model
locations, with `ESP32_LLM_WORKSPACE` as the artifact-root override. Keep source
paths and generated artifacts separate, and document renamed tools explicitly.

## Consequences

- Source organization can improve without changing the on-board protocol or model interpretation.
- Existing scripts that use old source paths must follow the [migration table](../repository-layout.md).
- Packing tests and flash-plan tests provide host regression evidence; hardware compatibility still needs a board run.
- Any future binary-format change requires an explicit version/migration decision and coordinated firmware/exporter updates.
- Release notes are written in English and state artifact contents, usage and verified scope. Documentation-only changes must not be presented as rebuilt firmware.

See [contributing](../../CONTRIBUTING.md) and [project scope](../product-spec.md).
