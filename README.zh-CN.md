<p align="center">
  <img src="docs/images/project-mark.svg" width="80" alt="Seven-board ESP32 cluster mark">
</p>

<h1 align="center">ESP32-LLM-001</h1>

<p align="center">在七块 ESP32-S3 上运行 Qwen2-0.5B 的实验性推理流水线。</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

<p align="center">
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest"><img src="https://img.shields.io/github/v/release/Crucifixion-Fxl/ESP32-LLM-001?color=087f8c" alt="Latest release"></a>
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/actions/workflows/ci.yml"><img src="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/actions/workflows/ci.yml/badge.svg" alt="Repository checks"></a>
  <img src="https://img.shields.io/badge/target-ESP32--S3_N16R8-334155" alt="Target: ESP32-S3 N16R8">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-334155" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest"><strong>下载固件与模型文件</strong></a> ·
  <a href="docs/getting-started.zh-CN.md">复现指南</a>
</p>

<p align="center">
  <img src="docs/images/architecture.svg" width="960" alt="One master and six four-layer compute nodes connected in an SPI ring">
</p>

## 项目特点

- **七块板，一个模型。** 主板协调六个计算节点，每个节点执行四层 Transformer，通过 SPI 传递数据。
- **紧凑的模型存储。** 三值权重（`−1、0、+1`）使用两位编码，词向量使用 INT4。
- **面向硬件的训练。** 推荐 QAT 训练器模拟计算节点使用的逐向量 INT8 激活量化。
- **完整可查的实现。** ESP-IDF 固件、模型准备、训练、二进制导出和主机检查集中在一个仓库。
- **可直接烧录的文件。** Release 提供主板固件、节点固件及模型文件，无需先自行编译或训练。

当前属于研究原型，生成内容可能重复或不连贯。详见[验证范围与限制](docs/architecture.md#validation-and-limitations)。

## 推理流程

| 阶段 | 职责 |
| --- | --- |
| 主板 → 节点 1 | 对输入分词，为每个 token 查询 INT4 词向量。 |
| 节点 1–6 | 依次执行第 0–23 层，通过 10 MHz SPI 传递 float32 隐藏状态。 |
| 节点 6 → 主板 | 返回隐藏状态，执行最终归一化、LM head 和采样。 |
| 下一个 token | 收到上一轮结果后，再次完成全部六个节点的计算。 |

权重保存在各自的板上；整条流水线按顺序执行。[架构与接线说明](docs/architecture.md)给出了数据通路和引脚定义。

## 环境要求

| 使用场景 | 所需条件 |
| --- | --- |
| 运行 Release | 7 × ESP32-S3 N16R8（每板 16 MB Flash / 8 MB 八线 PSRAM）、USB 数据线、跳线、合适的 5 V 电源、Python 和 `esptool`。 |
| 使用模型工具 | [uv](https://docs.astral.sh/uv/)、锁定的 Python 3.14 环境及模型文件；训练还需要相应计算资源。 |
| 编译固件 | ESP-IDF **v6.1-beta1** 和 ESP32-S3 工具链，使用其独立环境。 |
| 使用以下快捷命令 | GNU Make；指南也提供直接调用 Python 和 ESP-IDF 的方式。 |

## 安装

1. 从[最新 Release](https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest) 下载 `firmware-master.zip`、`firmware-node.zip` 和 `model-bins.zip`。
2. 为板子标记 **Master** 和 **Node 1–6**。断开复位级联线，逐板烧录。
3. 主板烧录主板固件、分词器、词向量和最终归一化参数；节点烧录通用节点固件及各自对应的四层模型文件。
4. 断电后，按[复现指南](docs/getting-started.zh-CN.md)连接 SPI 链、复位级联、就绪信号和公共地。

指南提供完整命令及地址。两份固件压缩包请分别解压：主板与节点的分区表文件同名，但内容不同。

## 日常使用

1. 为集群供电，以 **115200 波特率**打开主板 USB 串口。
2. 等待 `ALL NODE READY!!!` 和输入提示，输入简短提示词后按 Enter。
3. 查看生成文本与串口诊断。每个 token 都需要经过全部六个节点。

节点 KV 缓存上限为 512 token；主板分词输入缓冲另有 256 token 限制。节点启动时打印 64 项 ASM/C++ 车道对照结果；硬件验证时应比较数值，当前诊断不会因结果不一致而停止运行。

## 从源码构建

```bash
git clone https://github.com/Crucifixion-Fxl/ESP32-LLM-001.git
cd ESP32-LLM-001
make setup
make check
make test
```

在独立终端激活 ESP-IDF 环境，然后从仓库根目录执行：

```bash
make build          # 编译两种固件
make build-master   # 或只编译一种角色
make build-node
```

输出文件仍为 `master_board.bin` 和 `node_board.bin`；构建不会烧录设备。模型准备、训练、导出及指定串口烧录见[完整复现指南](docs/getting-started.zh-CN.md)。

`make help` 列出所有快捷命令。模型默认存放在 `Qwen2-0.5B/` 和 `cropped_Qwen/`；可通过 `ESP32_LLM_WORKSPACE` 指定其他目录。模型、数据集及检查点不纳入 Git。分析工具的可选依赖通过 `uv sync --locked --extra analysis` 安装。

## 历史实验结果

以下数据来自 **v1.0.0** 实验记录，并非每次提交重新测试的基准。详见[原始开发记录](docs/development-notes.zh-CN.md)。

| 项目 | 配置或记录值 |
| --- | --- |
| 模型 | Qwen2-0.5B；24 层；词表裁剪至 32,000 |
| 训练 | WikiText-103；4,000 步；验证损失 4.58 / 困惑度 97.8 |
| 生成速度 | 端到端约 7 秒/token |
| 功耗 | 待机约 1.2 W / 生成约 1.5 W |

## 项目结构

| 路径 | 职责 |
| --- | --- |
| [`firmware/master/`](firmware/master/) | 分词、词向量、最终归一化、采样及集群控制。 |
| [`firmware/node/`](firmware/node/) | 四层 Transformer 计算、内核及 SPI 传输。 |
| [`tools/`](tools/README.md) | 模型准备、QAT、导出、验证及分析。 |
| [`scripts/`](scripts/) | 指定串口烧录、容器训练及仓库维护。 |
| [`tests/`](tests/) | 二进制格式、烧录计划等主机回归检查。 |
| [`docs/`](docs/) | 部署、架构、项目范围、设计决策及图示。 |
| [`Makefile`](Makefile) | 常用开发命令入口。 |
| [`.github/`](.github/) | CI、Issue 和 Pull Request 模板。 |

改名后的脚本位置见[路径迁移指南](docs/repository-layout.md)。

## 常见问题

| 现象 | 检查项 |
| --- | --- |
| 无法烧录 | 串口、USB 数据线、BOOT/RST 顺序，以及复位级联线是否断开。 |
| PSRAM 或分区错误 | N16R8 硬件、SDK 默认配置、对应角色的分区表。 |
| 主板始终未就绪 | 复位级联，以及节点 6 GPIO 3 → 主板 GPIO 3。 |
| SPI 错误或首 token 长时间等待 | 节点 6 → 主板回程链路、信号线长度、供电和共地。 |
| 输出重复或不连贯 | 节点层文件分配、PC 冒烟输出及已知模型质量限制。 |
| 找不到模型文件 | `ESP32_LLM_WORKSPACE`、准备与导出顺序，以及[工具链指南](tools/README.md)中的路径。 |

## 文档

- [中文复现指南](docs/getting-started.zh-CN.md) · [English setup guide](docs/getting-started.md)
- [架构、接线和 Flash 布局](docs/architecture.md)
- [项目规格与验证范围](docs/product-spec.md)
- [模型工具链](tools/README.md) · [图源说明](docs/diagrams/README.md)
- [v1.0.0 发布说明（英文）](docs/releases/v1.0.0.md)
- [ADR 0001：七板推理流水线](docs/adr/0001-seven-board-pipeline.md)
- [ADR 0002：保持发布文件兼容](docs/adr/0002-release-artifact-compatibility.md)

## 参与贡献

欢迎聚焦问题的修复、可复现的硬件报告和文档改进。提交前运行 `make check` 和 `make test`，并分别说明固件编译与真实硬件验证结果。详见[贡献指南](CONTRIBUTING.md)。

## 致谢与许可

基于 [Low-Zi-Hong/ESP32s3-LLM-Cluster](https://github.com/Low-Zi-Hong/ESP32s3-LLM-Cluster) 的七板架构、固件基础和模型工具链，增加了乘加内核修复和激活量化感知训练流程。三值量化方法参考 [Microsoft BitNet](https://github.com/microsoft/BitNet)，基座模型来自 [Qwen2-0.5B](https://huggingface.co/Qwen/Qwen2-0.5B)。

仓库代码采用 [MIT 许可](LICENSE)，保留上游版权声明；模型权重与数据集遵循各自的上游许可。
