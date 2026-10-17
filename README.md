<p align="center">
  <img src="docs/images/project-mark.svg" width="80" alt="Seven-board ESP32 cluster mark">
</p>

<h1 align="center">ESP32-LLM-001</h1>

<p align="center">Experimental Qwen2-0.5B inference across seven ESP32-S3 boards.</p>

<p align="center">
  <a href="README.md"><strong>English</strong></a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest"><img src="https://img.shields.io/github/v/release/Crucifixion-Fxl/ESP32-LLM-001?color=087f8c" alt="Latest release"></a>
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/actions/workflows/ci.yml"><img src="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/actions/workflows/ci.yml/badge.svg" alt="Repository checks"></a>
  <img src="https://img.shields.io/badge/target-ESP32--S3_N16R8-334155" alt="Target: ESP32-S3 N16R8">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-334155" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest"><strong>Download firmware and model binaries</strong></a> ·
  <a href="docs/getting-started.md">Setup guide</a>
</p>

<p align="center">
  <img src="docs/images/architecture.svg" width="960" alt="One master and six four-layer compute nodes connected in an SPI ring">
</p>

## Highlights

- **Seven boards, one model.** A master coordinates six compute nodes, each running four transformer layers over SPI.
- **Compact model storage.** Ternary weights (`−1, 0, +1`) use two-bit codes; embeddings use INT4.
- **Hardware-aware training.** The primary QAT trainer simulates the per-vector INT8 activation quantization used by the node kernels.
- **Inspectable implementation.** ESP-IDF firmware, model preparation, training, binary export and host checks live in one repository.
- **Ready-to-flash artifacts.** The release includes master firmware, node firmware and model binaries; building or training is optional.

This is a research prototype. Generated text can repeat or be incoherent; see
[validation and limitations](docs/architecture.md#validation-and-limitations).

## Pipeline behavior

| Stage | Responsibility |
| --- | --- |
| Master → Node 1 | Tokenize a prompt and look up the INT4 embedding for each token. |
| Nodes 1–6 | Run layers 0–23 in sequence, passing float32 hidden states over 10 MHz SPI. |
| Node 6 → Master | Return the hidden state for final normalization, the LM head and sampling. |
| Next token | Repeat the full six-node pass after the previous result returns. |

Weights stay on their assigned boards. This is a serialized inference pipeline;
[architecture and wiring](docs/architecture.md) describe the data path and pin assignments.

## Requirements

| Use case | What you need |
| --- | --- |
| Run a release | 7 × ESP32-S3 N16R8 (16 MB flash / 8 MB octal PSRAM), USB data cable, jumper wires, suitable 5 V power, Python and `esptool`. |
| Use the model tools | [uv](https://docs.astral.sh/uv/), the locked Python 3.14 environment, and model artifacts. Training additionally needs suitable compute capacity. |
| Build firmware | ESP-IDF **v6.1-beta1** with ESP32-S3 tools, in its own activated environment. |
| Use the shortcuts below | GNU Make; direct Python and ESP-IDF commands are also documented in the guides. |

## Install

1. Download `firmware-master.zip`, `firmware-node.zip` and `model-bins.zip` from the [latest release](https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest).
2. Label the boards **Master** and **Node 1–6**. Flash each board individually with reset links disconnected.
3. Flash the master firmware and its tokenizer, embeddings and final norm. Flash the common node firmware and the correct four-layer binary to each node.
4. Power off, then connect the SPI chain, reset cascade, ready return and common ground using the [setup guide](docs/getting-started.md).

The guide contains exact commands and offsets. Extract the firmware archives
separately: master and node partition tables have the same filename but different contents.

## Everyday use

1. Power the cluster and open the master's USB serial console at **115200 baud**.
2. Wait for `ALL NODE READY!!!` and the prompt. Enter a short prompt and press Enter.
3. Inspect the generated text and serial diagnostics. Each token traverses all six nodes.

The node KV cache supports 512 tokens; the master's tokenizer input buffer has a
separate 256-token limit. Boot diagnostics print 64 ASM/C++ lane comparisons;
compare the values when validating hardware, as mismatches do not halt execution.

## Build from source

```bash
git clone https://github.com/Crucifixion-Fxl/ESP32-LLM-001.git
cd ESP32-LLM-001
make setup
make check
make test
```

Activate ESP-IDF in a separate shell, then run from the repository root:

```bash
make build          # Build both firmware projects
make build-master   # Or build one role
make build-node
```

Outputs remain `master_board.bin` and `node_board.bin`. Building does not flash
a board. Use the [source deployment guide](docs/getting-started.md#option-b-build-and-prepare-from-source)
for model preparation, training, export and explicit-port flashing.

`make help` lists all shortcuts. Model files default to `Qwen2-0.5B/` and
`cropped_Qwen/`; set `ESP32_LLM_WORKSPACE` to use another artifact directory.
Models, datasets and checkpoints are excluded from Git. Optional analysis tools
are installed with `uv sync --locked --extra analysis`.

## Reported results

Historical **v1.0.0** experiment results, not benchmarks rerun for each commit.
See the [original development notes (Chinese)](docs/development-notes.zh-CN.md).

| Item | Reported configuration / result |
| --- | --- |
| Model | Qwen2-0.5B; 24 layers; vocabulary cropped to 32,000 |
| Training | WikiText-103; 4,000 steps; validation loss 4.58 / perplexity 97.8 |
| Generation | Approximately 7 seconds per token, end to end |
| Power | Approximately 1.2 W idle / 1.5 W generating |

## Project layout

| Path | Responsibility |
| --- | --- |
| [`firmware/master/`](firmware/master/) | Tokenizer, embeddings, final norm, sampling and cluster control. |
| [`firmware/node/`](firmware/node/) | Four-layer transformer execution, kernels and SPI transport. |
| [`tools/`](tools/README.md) | Model preparation, QAT, export, validation and analysis. |
| [`scripts/`](scripts/) | Explicit-port flashing, container training and repository maintenance. |
| [`tests/`](tests/) | Host regression checks, including binary formats and flash plans. |
| [`docs/`](docs/) | Setup, architecture, project scope, decisions and generated diagrams. |
| [`Makefile`](Makefile) | Common development commands. |
| [`.github/`](.github/) | CI and issue / pull-request templates. |

Renamed scripts are listed in the [path migration guide](docs/repository-layout.md).

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Cannot flash a board | Serial port, USB data cable, BOOT/RST sequence and disconnected reset links. |
| PSRAM or partition error | N16R8 hardware, SDK defaults and the partition table for the correct board role. |
| Master never becomes ready | Reset cascade and Node 6 GPIO 3 → Master GPIO 3. |
| SPI errors or a long first-token stall | Node 6 → Master return hop, short signal wires, stable supply and common ground. |
| Repeated or incoherent output | Layer-file placement, host smoke output and the model's known quality limits. |
| Missing model files | `ESP32_LLM_WORKSPACE`, preparation/export order and paths in the [toolchain guide](tools/README.md). |

## Documentation

- [Setup and flashing](docs/getting-started.md) · [中文复现指南](docs/getting-started.zh-CN.md)
- [Architecture, wiring and flash layout](docs/architecture.md)
- [Project specification and validation scope](docs/product-spec.md)
- [Model toolchain](tools/README.md) · [Diagram sources](docs/diagrams/README.md)
- [v1.0.0 release notes](docs/releases/v1.0.0.md)
- [ADR 0001: seven-board inference pipeline](docs/adr/0001-seven-board-pipeline.md)
- [ADR 0002: preserve release artifact compatibility](docs/adr/0002-release-artifact-compatibility.md)

## Contributing

Focused fixes, reproducible hardware reports and documentation improvements are
welcome. Run `make check` and `make test`, and report firmware and physical-board
validation separately. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Attribution and license

Based on [Low-Zi-Hong/ESP32s3-LLM-Cluster](https://github.com/Low-Zi-Hong/ESP32s3-LLM-Cluster),
which provided the seven-board architecture, firmware foundation and initial
model tooling. Additional work includes the MAC-kernel correction and
activation-aware QAT workflow. The ternary-weight approach is informed by
[Microsoft BitNet](https://github.com/microsoft/BitNet); the base model is
[Qwen2-0.5B](https://huggingface.co/Qwen/Qwen2-0.5B).

Repository code is [MIT licensed](LICENSE), with upstream copyright preserved.
Model weights and datasets retain their respective upstream terms.
