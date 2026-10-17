# Master firmware

ESP-IDF project for **ESP32-S3 N16R8**, responsible for tokenization, INT4 embedding lookup, final RMS norm, LM head and sampling.

## Build and flash

Use ESP-IDF v6.1-beta1 with ESP32-S3 tools installed. After activating its
environment, run from the repository root:

```bash
idf.py -C firmware/master set-target esp32s3
idf.py -C firmware/master build
idf.py -C firmware/master -p PORT flash monitor
```

Output: `firmware/master/build/master_board.bin`. The application filename and
partition layout remain compatible with the v1.0.0 release. Flash model data
separately using the [setup guide](../../docs/getting-started.md).

## Source layout

`main/` is the ESP-IDF application component. Its primary files are `app_main.cpp`, `embedding.*`, `lm_head.*`, `tokenizer_types.h`, `model_types.h`, `spi_bus.*`.
`partitions.csv` defines flash addresses; `sdkconfig.defaults` records the
required 16 MB flash, octal PSRAM and console settings.

See [architecture and wiring](../../docs/architecture.md) before connecting boards.
A successful build is not an on-device inference test.
