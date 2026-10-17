# Contributing

Start with a focused issue describing the problem, hardware and reproduction
steps. For a pull request, keep unrelated model, firmware and documentation
changes separate and explain compatibility with existing release artifacts.

## Local setup and checks

From the repository root:

```bash
make setup
make check
make test
```

For firmware changes, activate ESP-IDF v6.1-beta1 and build the affected project:

```bash
make build-master
make build-node
```

Run `make help` for all shortcuts. Override `MASTER_BUILD` or `NODE_BUILD` to
build outside the default firmware build directories. For optional analysis
dependencies, use `uv sync --locked --extra analysis`.

Use `scripts/flash_data.py --dry-run` to review data-flash commands without a
serial device. A real flash requires an explicit port and the correct layer file.

## Conventions

- Python modules: descriptive `snake_case.py` names under the relevant `tools/`
  stage. Invoke them with `python -m tools.<stage>.<module>` from the root.
- Firmware: keep ESP-IDF's `main/` component convention; use `app_main.cpp` for
  entry points and descriptive headers such as `model_types.h`.
- Documentation: lowercase hyphenated filenames; `.zh-CN.md` for Chinese guides.
  Keep the two root READMEs aligned.
- New scripts must not embed personal paths, serial ports, container names or
  credentials. Model defaults should use `tools.paths`.
- Do not commit downloaded weights, datasets, checkpoints, build output or logs.
- Preserve upstream attribution and the existing license notice.

## Reporting validation

State which checks ran and which did not. Distinguish host unit tests, firmware
compilation, boot diagnostics and end-to-end seven-board inference. Include
board type, ESP-IDF version, artifact version, wiring and relevant serial logs
for hardware issues; redact local identifiers and credentials.

## Diagrams

Edit `scripts/render_diagrams.py`, regenerate SVGs, and visually review the
result. `--check` confirms that checked-in diagrams match their source.

## Documentation and releases

Keep English and Chinese READMEs aligned. Record current behavior in
[the project specification](docs/product-spec.md) and meaningful design decisions
under `docs/adr/`; label retrospective records as existing design.

Keep release-note source under `docs/releases/`. Write GitHub release titles
and notes in English. Describe the included files,
setup steps, compatibility, verified scope and known limitations. Separate
historical experiment results from new validation. Editing release notes must
not imply that firmware attachments were rebuilt or retested.
