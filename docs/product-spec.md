# Project specification

[Overview](../README.md) · [Architecture](architecture.md) · [Setup](getting-started.md)

This document describes the current implementation and its validation boundaries.
It is not a roadmap or a claim that every commit has been tested on hardware.

## Purpose

Explore Qwen2-0.5B inference using the memory and compute of seven ESP32-S3
microcontrollers. Users can flash the published model, inspect firmware kernels,
or reproduce the model preparation, QAT and export workflow.

The project is an experimental serial-console application. It does not provide
a web service, a general model loader or a production conversational assistant.

## Supported configuration

| Item | Current configuration |
| --- | --- |
| Boards | One master and six compute nodes; ESP32-S3 N16R8 on every board |
| Firmware toolchain | ESP-IDF v6.1-beta1; separate master and node projects |
| Host toolchain | Python 3.14 and dependencies recorded in `uv.lock` |
| Model | Qwen2-0.5B; 24 transformer layers; hidden dimension 896; 32,000-token cropped vocabulary |
| Weight formats | Ternary linear weights in two-bit codes; INT4 embeddings |
| Node activations | Per-vector INT8 quantization inside ternary matrix multiplication |
| Transport | 10 MHz SPI mode 0; 4,096-byte frames; 12-byte header; float32 hidden states |
| Limits | Node KV cache: 512 tokens; master tokenizer input buffer: 256 tokens |
| User interface | Master USB serial console, 115200 baud |

Model dimensions and partition layouts are compiled into the firmware. Supporting
other dimensions requires coordinated changes to exporters and firmware.

## Runtime contract

1. The master controls the reset cascade and waits for the final node's ready signal.
2. The master tokenizes input and embeds each token.
3. Nodes 1–6 execute four layers each, in physical order, using their own layer binaries.
4. The master receives the final hidden state, normalizes it, computes logits and samples.
5. Generation repeats this path for each token. There is no concurrent request scheduler.

The node image is shared; each node's model data differs. Firmware and model data
are flashed separately. The [architecture reference](architecture.md) defines
board responsibilities, wiring and partition offsets.

## Files and external services

Model tools use `Qwen2-0.5B/` and `cropped_Qwen/` under the repository by default.
`ESP32_LLM_WORKSPACE` relocates that artifact root. Checkpoints default to
`checkpoints/qat/`; a trainer option can override their location.

Preparation can download Qwen files; training can download WikiText-103. Once
flashed, inference uses local weights and the wired SPI chain. The documentation
does not promise that host preparation or training is an offline workflow.

## Validation levels

| Level | Evidence | Does not establish |
| --- | --- | --- |
| Repository checks | Python syntax, local links, SVG generation, CMake references and shell syntax | Successful firmware compilation or runtime behavior |
| Host tests | Packing/decoding fixtures, quantization checks, workspace paths and flash plans | Xtensa execution or physical wiring |
| CPU smoke check | Load decoded packed weights and generate text | Bit-exact full firmware emulation, including INT8 activations |
| Firmware build | Master and node binaries compile and fit their configured app partitions | Successful boot or inference on boards |
| Board diagnostics | Inspect 64 printed ASM/C++ comparisons and startup signals | Automatic failure detection; the comparisons only print results |
| End-to-end hardware run | Record board/artifact versions, wiring, serial logs and generated text | General model quality or a reproducible benchmark without recorded conditions |

Historical v1.0.0 notes report roughly 7 seconds per token, 1.2 W idle and 1.5 W
while generating. Repetition, incoherent output, return-link corruption and long
first-token stalls were also observed. Treat these as historical observations,
not release-by-release acceptance results.

## Compatibility and maintenance

Preserve existing release filenames and binary layouts when changing source
organization. Intentional format changes need explicit migration instructions
and coordinated firmware/exporter validation. See the [design decisions](adr/0002-release-artifact-compatibility.md).
