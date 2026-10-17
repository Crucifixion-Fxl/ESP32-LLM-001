# Model toolchain

Run all modules from the repository root with `uv run python -m ...`.
Defaults come from [paths.py](paths.py), not the current tool directory. The
workspace defaults to the repository root; `ESP32_LLM_WORKSPACE` overrides it.

## Recommended pipeline

```bash
uv sync --locked
# Downloads missing base files; then crops tokenizer and embedding rows.
uv run python -m tools.prepare.prepare_colab
uv run python -m tools.training.train_qat --steps 4000
uv run python -m tools.export.quantize_embeddings
uv run python -m tools.export.pack_tokenizer
uv run python -m tools.export.pack_weights
uv run python -m tools.validation.validate_int4
```

| Stage | Module | Input → output |
| --- | --- | --- |
| Crop tokenizer | `tools.prepare.crop_tokenizer` | `Qwen2-0.5B/` → tokenizer/config in `cropped_Qwen/` |
| Crop embeddings | `tools.prepare.crop_weights` | Base weights → `cropped_Qwen/model.safetensors` |
| Train | `tools.training.train_qat` | Cropped model → `qwen_158.safetensors` |
| INT4 embeddings | `tools.export.quantize_embeddings` | Ternary checkpoint → `qwen_158_int4.safetensors` |
| Pack tokenizer | `tools.export.pack_tokenizer` | `tokenizer.json` → `tokenizer.bin` |
| Pack weights | `tools.export.pack_weights` | INT4/ternary checkpoint → `bins/` |
| CPU smoke run | `tools.validation.validate_int4` | Decode packed weights and generate a short sample |

The CPU smoke run does not emulate the full firmware or INT8 activation path.
All format-sensitive changes require host regression checks plus physical-board
validation before claiming numerical parity.

## Training and checkpoints

```bash
uv run python -m tools.training.train_qat --help
uv run python -m tools.training.train_qat --resume --steps 50000
# Resume an existing checkpoint directory explicitly:
uv run python -m tools.training.train_qat --resume --ckpt /path/to/checkpoint
```

The default checkpoint directory is `<workspace>/checkpoints/qat/`. Training
uses WikiText-103 and selects CUDA, MPS or CPU as available. Larger runs are
expected to use a GPU; no runtime or quality guarantee is implied.

`--model-dir` and `--export-path` can select explicit paths; when overriding the
model directory, pass the export path too if it should move with the input.

For a preconfigured CUDA container image with these Python dependencies installed:

```bash
bash scripts/train_container.sh YOUR_CUDA_IMAGE --steps 4000
```

The launcher mounts only the repository at `/workspace`, creates a temporary
container and never removes an existing named container. `GPUS` selects Docker's
GPU argument. It does not provision a remote server or install dependencies.

## Analysis and experiments

Install plot dependencies with `uv sync --locked --extra analysis`.

| Module | Purpose |
| --- | --- |
| `tools.analysis.analyze_weights` | Safetensors distribution plots; accepts a file argument and `--help` |
| `tools.analysis.inspect_tensors` | Tensor names, shapes and dtypes |
| `tools.analysis.inspect_memory` | Packed checkpoint storage and embedding details |
| `tools.analysis.analyze_sparsity` | Ternary-code distribution in a binary file |
| `tools.analysis.inspect_tokenizer` | Token IDs for a small demonstration prompt |
| `tools.inference.generate` | Interactive inference with the older host decode path |
| `tools.prepare.update_model_config` | Reapply cropped vocabulary/token IDs to a config |

[experiments/](experiments/README.md) retains earlier training and decoding
variants for comparison. These are intentionally separated from the recommended
pipeline; do not overwrite a deployment checkpoint with an experimental export.
