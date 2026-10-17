# Architecture

[Project overview](../README.md) · [Setup](getting-started.md) · [Toolchain](../tools/README.md)

## Runtime topology

![Seven-board inference pipeline](images/architecture.svg)

The master embeds one token into a 896-element hidden state. Six nodes process
four transformer layers each, in order. Node 6 returns the final hidden state to
the master for final RMS normalization, a tied embedding/LM head, and sampling.
The next token repeats the same circuit. This is serialized pipeline inference,
not seven independent replicas and not concurrent batching.

| Board | Responsibility | Model data |
| --- | --- | --- |
| Master | BPE tokenizer, INT4 embeddings, final norm, LM head, sampling | `tokenizer.bin`, `embed.bin`, `final_norm.bin` |
| Node 1 | Layers 0–3 | `layers_0_to_3.bin` |
| Node 2 | Layers 4–7 | `layers_4_to_7.bin` |
| Node 3 | Layers 8–11 | `layers_8_to_11.bin` |
| Node 4 | Layers 12–15 | `layers_12_to_15.bin` |
| Node 5 | Layers 16–19 | `layers_16_to_19.bin` |
| Node 6 | Layers 20–23 | `layers_20_to_23.bin` |

Both firmware projects use a 4,096-byte SPI transaction buffer, a 12-byte frame
header, and 10 MHz SPI mode 0. Hidden states are float32; quantized weights stay
local to each board. The node kernels quantize activation vectors to INT8 before
ternary matrix multiplication.

## Wiring

![GPIO connections, reset cascade, ready return and common ground](images/wiring.svg)

For each data hop, including **Node 6 → Master**:

| Signal | Upstream output | Downstream input |
| --- | --- | --- |
| CS | GPIO 4 | GPIO 15 |
| MOSI | GPIO 5 | GPIO 16 |
| SCLK | GPIO 7 | GPIO 18 |

These are GPIO numbers, not physical header positions. There is no MISO wire on
a hop: the return uses the next board's independent SPI transmitter.

- Reset cascade: Master GPIO 1 → Node 1 EN; then Node 1 GPIO 1 → Node 2 EN,
  continuing to Node 6. Node 6 GPIO 1 is unconnected.
- Ready return: Node 6 GPIO 3 → Master GPIO 3.
- All boards and the external supply must share ground.
- Disconnect reset-cascade connections while flashing a board. Keep signal leads
  short and avoid back-powering a board from USB and external 5 V simultaneously.

Pin definitions: [master SPI](../firmware/master/main/spi_bus.h),
[node SPI](../firmware/node/main/spi_bus.h), [master startup](../firmware/master/main/app_main.cpp),
[node startup](../firmware/node/main/app_main.cpp).

## Flash data layout

| Role | Address | File | Reserved region |
| --- | --- | --- | --- |
| Both | `0x10000` | Application firmware | `0x80000` bytes |
| Master | `0x90000` | `tokenizer.bin` | `0xC0000` bytes |
| Master | `0x150000` | `embed.bin` | `0xEA0000` bytes |
| Master | `0xFF0000` | `final_norm.bin` | `0x10000` bytes |
| Node | `0x90000` | Its four-layer binary | `0xF70000` bytes |

The partition CSV files are authoritative:
[master](../firmware/master/partitions.csv), [node](../firmware/node/partitions.csv).
Changing model dimensions or binary layouts requires coordinated exporter and
firmware changes; merely changing a model configuration file is insufficient.

## Model workflow

![Preparation to deployment](images/model-workflow.svg)

The primary trainer is [train_qat.py](../tools/training/train_qat.py). It trains
ternary linear layers with simulated INT8 activation quantization. Export stores
four ternary codes in each byte and INT4 embeddings in low/high nibbles. The
exported data layout is kept compatible with the v1.0.0 firmware.

## Validation and limitations

- Host tests cover binary packing, INT4 decoding, script paths and flash-command
  construction. They do not run the Xtensa assembly or communicate with boards.
- `tools.validation.validate_int4` loads decoded ternary weights and
  firmware-format INT4 embeddings into a CPU model. It **does not emulate**
  per-vector INT8 activations or all firmware numerics, so it is a smoke check,
  not a bit-exact golden reference.
- Node boot logs print 64 ASM/C++ lane comparisons (`UNIT r...`). The current
  diagnostic logs results; it does not assert or halt on a mismatch. Compare
  the values when validating a physical build.
- The node KV cache is configured for 512 tokens; the master's tokenizer buffer
  has a separate 256-token limit. Model dimensions are compiled into the firmware.
- Historical output shows repetition and incoherence. Additional training is
  not a guarantee of a particular generation quality.
- Historical return-link corruption remains a hardware troubleshooting item.
  This repository restructure does not claim a new on-board performance result.

Diagrams are regenerated with `python scripts/render_diagrams.py`; see
[diagram sources](diagrams/README.md).
