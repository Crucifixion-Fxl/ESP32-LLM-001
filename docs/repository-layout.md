# Repository layout and path migration

The restructure separates firmware, model stages, operational scripts and
reference documentation. ESP-IDF keeps its standard `main/` component directory;
firmware binary names and flash offsets have not changed.

Python tools are modules: use `uv run python -m tools.<stage>.<name>` from the
repository root instead of changing into `tools/` and running a bare filename.
Downloaded models stay in `Qwen2-0.5B/` and `cropped_Qwen/`; no model-data move is
required. `ESP32_LLM_WORKSPACE` overrides the default artifact root.

## Renamed and moved files

| Previous path | Current path |
| --- | --- |
| `tools/crop_token.py` | [`tools/prepare/crop_tokenizer.py`](../tools/prepare/crop_tokenizer.py) |
| `tools/crop_model_weight.py` | [`tools/prepare/crop_weights.py`](../tools/prepare/crop_weights.py) |
| `tools/colab_prepare.py` | [`tools/prepare/prepare_colab.py`](../tools/prepare/prepare_colab.py) |
| `tools/update_config.py` | [`tools/prepare/update_model_config.py`](../tools/prepare/update_model_config.py) |
| `tools/qat_speak.py` | [`tools/training/train_qat.py`](../tools/training/train_qat.py) |
| `tools/qat_158.py` | [`tools/experiments/train_qat_baseline.py`](../tools/experiments/train_qat_baseline.py) |
| `tools/qat_better.py` | [`tools/experiments/train_qat_weights_only.py`](../tools/experiments/train_qat_weights_only.py) |
| `tools/bit4_embedding.py` | [`tools/export/quantize_embeddings.py`](../tools/export/quantize_embeddings.py) |
| `tools/pack_tokenizer_bin.py` | [`tools/export/pack_tokenizer.py`](../tools/export/pack_tokenizer.py) |
| `tools/pack_model_bin.py` | [`tools/export/pack_weights.py`](../tools/export/pack_weights.py) |
| `tools/verify_int4_pc.py` | [`tools/validation/validate_int4.py`](../tools/validation/validate_int4.py) |
| `tools/run_model158.py` | [`tools/inference/generate.py`](../tools/inference/generate.py) |
| `tools/analyze_model.py` | [`tools/analysis/analyze_weights.py`](../tools/analysis/analyze_weights.py) |
| `tools/look_model_structure.py` | [`tools/analysis/inspect_tensors.py`](../tools/analysis/inspect_tensors.py) |
| `tools/size_model.py` | [`tools/analysis/inspect_memory.py`](../tools/analysis/inspect_memory.py) |
| `tools/check_zero.py` | [`tools/analysis/analyze_sparsity.py`](../tools/analysis/analyze_sparsity.py) |
| `tools/workplace.py` | [`tools/analysis/inspect_tokenizer.py`](../tools/analysis/inspect_tokenizer.py) |
| `tools/model_analyze_debugging/analyze_m.py` | [`tools/experiments/compare_int4_offset.py`](../tools/experiments/compare_int4_offset.py) |
| `tools/deploy_4090.sh` | [`scripts/train_container.sh`](../scripts/train_container.sh) |
| `firmware/node/flash.bat` | [`scripts/flash_nodes.bat`](../scripts/flash_nodes.bat) |
| `docs/REPRODUCE.md` | [`docs/getting-started.zh-CN.md`](../docs/getting-started.zh-CN.md) |
| `docs/JOURNEY.md` | [`docs/development-notes.zh-CN.md`](../docs/development-notes.zh-CN.md) |
| `firmware/master/main/main.cpp` | [`firmware/master/main/app_main.cpp`](../firmware/master/main/app_main.cpp) |
| `firmware/master/main/model_struct.h` | [`firmware/master/main/model_types.h`](../firmware/master/main/model_types.h) |
| `firmware/node/main/main.cpp` | [`firmware/node/main/app_main.cpp`](../firmware/node/main/app_main.cpp) |
| `firmware/node/main/model_struct.h` | [`firmware/node/main/model_types.h`](../firmware/node/main/model_types.h) |
| `firmware/master/main/struct.h` | [`firmware/master/main/tokenizer_types.h`](../firmware/master/main/tokenizer_types.h) |
| `firmware/node/main/debug.h` | [`firmware/node/main/tensor_debug.h`](../firmware/node/main/tensor_debug.h) |
| `firmware/node/main/lut_table.h` | [`firmware/node/main/ternary_lut.h`](../firmware/node/main/ternary_lut.h) |
| `firmware/node/main/lut_table.cpp` | [`firmware/node/main/ternary_lut.cpp`](../firmware/node/main/ternary_lut.cpp) |

## Consolidated or removed scaffolding

- `tools/flash_data.sh` and four hardcoded-port `flash_*.bat` scripts are replaced
  by [scripts/flash_data.py](../scripts/flash_data.py), with explicit role/port,
  node-layer validation and `--dry-run`. Model directory conventions are unchanged.
- The personal GPU-container helper is now `scripts/train_container.sh`: supply
  a prepared image; it no longer deletes a named container or mounts a home directory.
- The unused `src/llm` Hello World package and `llm` console entry point were
  removed. The repository is a firmware-and-tools workspace, not a published SDK.
- ESP-IDF `pytest_hello_world.py` templates were removed: they asserted output
  this firmware never emits. Host checks are in `tests/`; board diagnostics are
  documented separately.
- Training checkpoints now default to `checkpoints/qat/`. Existing checkpoints
  remain usable with `--ckpt /path/to/previous/checkpoint --resume`.
- License and upstream attribution remain intact. Historical notes retain old
  names to preserve their context; use this table for current locations.
