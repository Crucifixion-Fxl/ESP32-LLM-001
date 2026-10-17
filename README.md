<p align="center">
  <h1 align="center">ESP32-LLM-001</h1>
</p>

<p align="center">
  A 1.58-bit large language model running as a pipeline across seven ESP32-S3 boards —<br>
  speaking English at ~7 seconds per token on under 2 watts of power.
</p>

<p align="center">
  <a href="README.md"><strong>English</strong></a> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest"><img src="https://img.shields.io/github/v/release/Crucifixion-Fxl/ESP32-LLM-001?display_name=tag" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">
  <img src="https://img.shields.io/badge/target-ESP32--S3%20N16R8-e7352b" alt="ESP32-S3 N16R8">
  <img src="https://img.shields.io/badge/model-Qwen2--0.5B%20%C2%B71.58--bit-615fff" alt="Qwen2-0.5B 1.58-bit">
  <img src="https://img.shields.io/badge/speed-~7%20s%20%2F%20token-0ea5e9" alt="~7 s per token">
</p>

<p align="center">
  <img src="docs/images/architecture.svg" alt="ESP32-LLM-001 cluster architecture: one master board handles tokenization, embeddings and sampling; six compute nodes each run four 1.58-bit transformer layers, chained over 3-wire SPI hops">
</p>

## Highlights

- Runs a real 0.5B-parameter decoder (Qwen2-0.5B, vocabulary cropped to 32K) on seven
  ~¥30 microcontroller boards, with **1.58-bit ternary weights** and INT4 embeddings.
- Six compute nodes execute four transformer layers each — attention with RoPE and
  grouped-query KV cache in PSRAM, SwiGLU MLP — over a 3-wire SPI daisy chain.
- Fixed a silent firmware bug from the upstream project where **75% of weights never
  participated in inference** (see below); rewrote the Xtensa EE assembly MAC kernel,
  validated by a 64-case lane-level unit test that now runs at every boot.
- Trains with the **deployment arithmetic baked in**: per-vector int8 activation
  quantization is simulated during QAT, so what the GPU validates is what the
  boards compute.
- `verify_int4_pc.py` reproduces the exact board arithmetic on a PC — a golden
  reference you run before flashing.
- Complete tooling: resume-able training with early stopping and best-checkpoint
  export, one-command macOS flashing scripts, and a reproduction manual that takes
  a fresh board set to a talking cluster in ~40 minutes using Release binaries.

## Performance

| Metric | Value |
| --- | --- |
| Model | Qwen2-0.5B → 32K vocab → 1.58-bit ternary + INT4 embeddings |
| Training | wikitext-103 · 4,000 steps · **val loss 4.58 / PPL 97.8** |
| Inference | ~7 s/token end-to-end · 1.04 s per node per 4 layers (55.6M MAC) |
| Power | ~1.2 W idle · ~1.5 W generating |
| Hardware cost | 7 × ESP32-S3-N16R8 ≈ ¥210 + jumper wires and a breadboard ≈ ¥10 |
| Context / vocab | 512 tokens / 32K (16 MB flash ceiling) |

Sample output (temperature 0.4):

```text
User > The capital of France is
Cluster > "...the largest ... city . ... in the 1980s ,
           the ... building is the ... highest known as the 2 0 0 0 0 0 0 0 0 ..."
```

A PPL-98 model with temperature sampling: semantic islands wrapped in numerical
daydreaming. Train longer and it improves — the pipeline stays identical.

## Getting started

- **[docs/REPRODUCE.md](docs/REPRODUCE.md)** — the zero-to-talking-cluster manual:
  bill of materials, every command, wiring tables, and a troubleshooting catalogue.
- **[Releases](../../releases)** — flashable firmware and model binaries (v1.0.0),
  no training required.

```bash
pip3 install esptool
# Master board (plug it in alone)
python3 -m esptool --chip esp32s3 --port PORT -b 921600 write_flash \
  0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 master_board.bin
python3 -m esptool --chip esp32s3 --port PORT -b 2000000 write_flash \
  0x90000 tokenizer.bin 0x150000 embed.bin 0xFF0000 final_norm.bin
# Then flash each of the six nodes with node firmware + its layers_*.bin,
# wire the chain, power up, and open the serial console at 115200.
```

## What this repository contributes

**1. A silent 75%-weight-loss fix in the assembly MAC kernel.**
The upstream firmware assembled operands for `ee.vmulas.s8.accx` with four
consecutive `ee.movi.32.q` writes into a single Q register. On ESP32-S3 that
instruction *replaces the whole register* (zero-filling the rest) and the MAC
consumes only the low 32 bits — so three of four weight words were erased and
the survivor was lane-misaligned. No crash, no error: just degenerate output.
We characterized the effective permutation with an impulse-sweep lane test
(σ(0)=12 … σ(3)=15, lanes 4–15 dead), rewrote the kernel as *one word per
register, four vmulas per group*, and froze the unit test into boot-time
self-check.

**2. Training that sees deployment arithmetic.**
The firmware quantizes activations to per-vector int8 before every ternary
matmul. Upstream QAT only ternarized weights, so GPU-side validation could not
predict board behavior. `tools/qat_speak.py` replicates `quantize_X` bit-for-bit
inside the training forward pass (±127 clamp, dead-zone guard, STE gradients).

## Repository layout

```text
├── README.md / README.zh-CN.md   # you are here (EN / 简体中文)
├── docs/
│   ├── REPRODUCE.md              # zero-to-cluster reproduction manual
│   ├── JOURNEY.md                # full build & debugging chronicle
│   └── images/                   # diagrams
├── firmware/
│   ├── master/                   # ESP-IDF project: tokenizer, embeddings, LM head, SPI
│   └── node/                     # ESP-IDF project: 4-layer transformer worker
│       └── main/bitlinear_forward_q.S   # fixed assembly MAC kernel
└── tools/
    ├── qat_speak.py              # deployment-aligned QAT (resume / early stop / best export)
    ├── verify_int4_pc.py         # PC-side golden reference of board arithmetic
    ├── flash_data.sh             # macOS data-partition flashing
    ├── colab_prepare.py          # one-shot model prep for Colab
    ├── deploy_4090.sh            # GPU-server deployment helper
    └── crop_*.py, bit4_*.py, pack_*.py  # upstream quantization & packing pipeline
```

## Known limitations

- First token occasionally stalls ~3 minutes then fails a magic check — suspected
  marginal jumper on the Node6→Master return segment; the master firmware prints
  raw bytes of any corrupt frame to help localize it.
- Repetition bias persists at temperature 0.4; adjustable in
  `firmware/master/main/main.cpp` (`lm_head_sample(..., 0.4f)`).
- 64 tokens take ~8 minutes — the honest cost of a serialized 6-hop pipeline.

## Acknowledgments

- **[Low-Zi-Hong/ESP32s3-LLM-Cluster](https://github.com/Low-Zi-Hong/ESP32s3-LLM-Cluster)** —
  the architectural foundation of this project: the 7-board SPI daisy-chain design,
  the 1.58-bit firmware skeleton, and the PC-side toolchain all originate there.
  The ASM fix and training methodology documented here are incremental work on
  top of it.
- [microsoft/BitNet](https://github.com/microsoft/BitNet) — the 1.58-bit ternary
  quantization idea.
- The Qwen team — the Qwen2-0.5B base model.

## License

MIT, inherited from upstream. Derivatives of Qwen2-0.5B weights follow the
upstream model license.
