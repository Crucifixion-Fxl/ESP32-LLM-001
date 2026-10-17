# 复现指南

[项目主页](../README.zh-CN.md) · [English](getting-started.md) · [架构与接线](architecture.md)

## 准备硬件与环境

需要七块 **ESP32-S3 N16R8**（每块 16 MB Flash、8 MB 八线 PSRAM）、USB 数据线、短杜邦线和稳定的 5 V 电源。先将开发板标为 Master、Node 1–6；节点位置与层文件必须一致。

烧录 Release 只需要 Python 和 esptool：`python -m pip install esptool`。
源码工具使用 `uv sync --locked` 安装锁定的 Python 3.14 环境；编译固件使用独立的 **ESP-IDF v6.1-beta1** 环境。参考 [ESP-IDF 安装说明](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/)。

## 路径一：直接使用 Release

从 [v1.0.0](https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/tag/v1.0.0) 下载：

| 文件 | 内容 |
| --- | --- |
| `firmware-master.zip` | 主板 bootloader、分区表、应用固件 |
| `firmware-node.zip` | 计算节点 bootloader、分区表、应用固件 |
| `model-bins.zip` | 分词器、词向量、最终归一化及六组层文件 |

三个压缩包分别解压，避免混用分区表。下列命令在包含对应文件的目录执行，也可以改用完整路径。`PORT` 替换为实际串口，例如 macOS 的 `/dev/cu.usbmodemXXXX`、Linux 的 `/dev/ttyACM0` 或 Windows 的 `COM3`。

### 主板

从主板固件目录执行：

```bash
python -m esptool --chip esp32s3 --port PORT --baud 921600 write-flash \
  0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 master_board.bin
```

再从模型文件目录执行：

```bash
python -m esptool --chip esp32s3 --port PORT --baud 2000000 write-flash \
  0x90000 tokenizer.bin 0x150000 embed.bin 0xFF0000 final_norm.bin
```

### 六个计算节点

每次连接一块节点，烧录相同的节点固件，再烧录它对应的层数据：

```bash
python -m esptool --chip esp32s3 --port PORT --baud 921600 write-flash \
  0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 node_board.bin
python -m esptool --chip esp32s3 --port PORT --baud 2000000 write-flash \
  0x90000 layers_0_to_3.bin
```

| 节点 | 层文件 |
| --- | --- |
| Node 1 | `layers_0_to_3.bin` |
| Node 2 | `layers_4_to_7.bin` |
| Node 3 | `layers_8_to_11.bin` |
| Node 4 | `layers_12_to_15.bin` |
| Node 5 | `layers_16_to_19.bin` |
| Node 6 | `layers_20_to_23.bin` |

## 路径二：从源码准备模型

以下命令始终在仓库根目录运行，不需要切换到 `tools/`：

```bash
git clone https://github.com/Crucifixion-Fxl/ESP32-LLM-001.git
cd ESP32-LLM-001
uv sync --locked
uv run python -m tools.prepare.prepare_colab
uv run python -m tools.training.train_qat --steps 4000
uv run python -m tools.export.quantize_embeddings
uv run python -m tools.export.pack_tokenizer
uv run python -m tools.export.pack_weights
uv run python -m tools.validation.validate_int4
```

准备脚本下载缺失的 Qwen2-0.5B 文件，然后裁剪分词器和词向量；训练阶段会下载 WikiText-103，并消耗 GPU 时间。训练默认检查点为 `checkpoints/qat/`，可追加 `--resume` 续跑。使用旧检查点时传入 `--ckpt /path/to/old/checkpoint`。

产物保存在 `cropped_Qwen/`。设置 `ESP32_LLM_WORKSPACE` 可改变模型与检查点的存放位置。PC 验证只检查解码、加载和生成，不完整模拟固件数值路径。详细说明见[工具链文档](../tools/README.md)。

Colab 使用同样的模块命令：先克隆仓库并 `%cd ESP32-LLM-001`，在运行时安装 `torch transformers safetensors accelerate datasets tqdm`，再执行 `!python -m tools.prepare.prepare_colab` 和训练命令。Colab 自带的 Python/依赖环境不等同于本仓库锁定环境，需要单独验证。

## 编译与烧录源码固件

激活 ESP-IDF 环境后，在仓库根目录执行：

```bash
idf.py -C firmware/master set-target esp32s3
idf.py -C firmware/master build
idf.py -C firmware/node set-target esp32s3
idf.py -C firmware/node build
idf.py -C firmware/master -p PORT flash
# 更换连接的开发板，再逐块烧录节点固件：
idf.py -C firmware/node -p PORT flash
```

数据分区另行烧录。先检查命令，不连接硬件也可执行：

```bash
uv run python scripts/flash_data.py master --port PORT --dry-run
uv run python scripts/flash_data.py node --port PORT --layer layers_0_to_3.bin --dry-run
```

确认后去掉 `--dry-run`。脚本要求 `cropped_Qwen/tokenizer.bin` 和 `cropped_Qwen/bins/` 下的模型文件；使用 `--model-dir` 可指定其他目录。Release 解压文件可直接使用前面的 esptool 命令。

## 接线与启动

![SPI、复位、就绪与共地接线](images/wiring.svg)

1. 断电后接线。每段 SPI 为上游 `GPIO 4/5/7` → 下游 `GPIO 15/16/18`，分别对应 CS/MOSI/SCLK。总共七段，包含 **Node 6 → Master** 回程。
2. Master 到 Node 6 依次连接上游 `GPIO 1` → 下游 `EN`；Node 6 的 GPIO 1 不接。
3. Node 6 的 `GPIO 3` 接 Master 的 `GPIO 3`，所有开发板与电源共地。
4. 烧录时断开复位级联。不要同时通过 USB 和外部 5 V 给同一块板供电。
5. 上电后以 115200 波特率查看主板串口，等待就绪后输入短提示词。

节点启动会打印 `UNIT begin`、64 项 ASM/C++ 比较和 `UNIT end`；主板就绪日志为 `ALL NODE READY!!!`。目前诊断只打印结果，不会自动断言失败；请对照数值并检查实际生成输出。

## 常见问题

| 现象 | 优先检查 |
| --- | --- |
| 无法进入下载模式 | 串口、USB 数据线、复位级联是否断开；BOOT/RST 操作 |
| PSRAM/分区报错 | 是否 N16R8，SDK 默认配置及主板/节点分区表是否对应 |
| 主板一直等待就绪 | 复位级联与 Node 6 GPIO 3 → Master GPIO 3 |
| 魔数校验失败、首 token 长时间等待 | 最后一段回程 SPI、杜邦线长度、共地和供电 |
| 输出重复或不连贯 | 层文件与物理位置、PC 解码验证输出、模型本身的质量限制 |
| 找不到模型文件 | 仓库根目录执行、工作区路径、是否完成上游准备步骤 |

原始实验过程保存在[开发记录](development-notes.zh-CN.md)，其中的历史性能数据不代表本次目录整理重新完成了七板硬件测试。
