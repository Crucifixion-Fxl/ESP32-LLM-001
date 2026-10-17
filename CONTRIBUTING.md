# Contributing

Start with a focused issue describing the problem, hardware and reproduction
steps. For a pull request, keep unrelated model, firmware and documentation
changes separate and explain compatibility with existing release artifacts.

## Local setup and checks

From the repository root:

```bash
uv sync --locked --extra analysis
uv run python -m unittest discover -s tests -v
uv run python scripts/check_repository.py
uv run python scripts/render_diagrams.py --check
```

For firmware changes, activate ESP-IDF v6.1-beta1 and build the affected project:

```bash
idf.py -C firmware/master build
idf.py -C firmware/node build
```

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
