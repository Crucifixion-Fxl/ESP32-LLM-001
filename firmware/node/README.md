# Node firmware

ESP-IDF project for **ESP32-S3 N16R8**, responsible for four transformer layers, ternary MAC kernels, attention and the local KV cache.

## Build and flash

Use ESP-IDF v6.1-beta1 with ESP32-S3 tools installed. After activating its
environment, run from the repository root:

```bash
idf.py -C firmware/node set-target esp32s3
idf.py -C firmware/node build
idf.py -C firmware/node -p PORT flash monitor
```

Output: `firmware/node/build/node_board.bin`. The application filename and
partition layout remain compatible with the v1.0.0 release. Flash model data
separately using the [setup guide](../../docs/getting-started.md).

## Source layout

`main/` is the ESP-IDF application component. Its primary files are `app_main.cpp`, `bitlinear.*`, `bitlinear_forward*.S`, `qwen_attention.*`, `ternary_lut.*`, `model_types.h`, `spi_bus.*`.
`partitions.csv` defines flash addresses; `sdkconfig.defaults` records the
required 16 MB flash, octal PSRAM and console settings.

See [architecture and wiring](../../docs/architecture.md) before connecting boards.
A successful build is not an on-device inference test.
