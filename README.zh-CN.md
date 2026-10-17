# ESP32-LLM-001

**在七块 ESP32-S3 上运行 Qwen2-0.5B 的实验性推理流水线。**

[English](README.md) · [复现指南](docs/getting-started.zh-CN.md) · [架构说明](docs/architecture.md) · [Releases](https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases) · [参与贡献](CONTRIBUTING.md)

![ESP32-S3 N16R8](https://img.shields.io/badge/target-ESP32--S3_N16R8-0f766e)
[![MIT](https://img.shields.io/badge/license-MIT-334155)](LICENSE)
![实验阶段](https://img.shields.io/badge/status-experimental-9a6700)

![集群架构：主板与六个四层计算节点通过 SPI 构成闭合数据通路](docs/images/architecture.svg)

## 项目概述

本项目探索低成本微控制器上的本地语言模型推理。主板负责分词、词向量查询、最终归一化和采样；六个计算节点分别执行四层 Transformer，通过 SPI 传递隐藏状态，最后一个节点将结果送回主板。

模型使用三值权重（`−1、0、+1`，以两位编码存储）、INT4 词向量和计算内核中的逐向量 INT8 激活量化。固件包含 Xtensa 乘加内核修复及启动时的 64 项车道诊断；推荐的 QAT 训练脚本会模拟固件的激活量化。

**当前属于研究原型，并非通用对话助手。** 生成内容可能重复或不连贯。PC 验证工具检查压缩权重的解码与加载，并不完整模拟整条固件数值路径。具体边界见[验证范围与限制](docs/architecture.md#validation-and-limitations)。

## 从这里开始

| 目标 | 文档或入口 |
| --- | --- |
| 使用现成固件和模型搭建七板集群 | [中文复现指南](docs/getting-started.zh-CN.md) |
| 阅读英文部署步骤 | [Getting started](docs/getting-started.md) |
| 准备、训练、导出模型 | [工具链说明](tools/README.md) |
| 从源码编译固件 | [主板](firmware/master/README.md) · [计算节点](firmware/node/README.md) |
| 了解架构、接线和存储布局 | [架构说明](docs/architecture.md) |
| 查找改名后的文件 | [目录与路径迁移](docs/repository-layout.md) |

### 主机环境

以下命令均在仓库根目录执行。锁定的主机环境使用 Python 3.14；ESP-IDF 使用独立的 Python 环境。

```bash
git clone https://github.com/Crucifixion-Fxl/ESP32-LLM-001.git
cd ESP32-LLM-001
uv sync --locked
uv run python -m tools.training.train_qat --help
uv run python scripts/flash_data.py --help
```

模型、检查点和二进制文件不提交到 Git。原有 `Qwen2-0.5B/` 与 `cropped_Qwen/` 目录继续可用；可通过 `ESP32_LLM_WORKSPACE` 指定其他存储目录。

### 固件编译

安装并激活 ESP-IDF v6.1-beta1 后：

```bash
idf.py -C firmware/master set-target esp32s3
idf.py -C firmware/master build
idf.py -C firmware/node set-target esp32s3
idf.py -C firmware/node build
```

固件输出仍为 `master_board.bin` 和 `node_board.bin`，与 v1.0.0 发布文件兼容。固件和模型数据需要分别烧录，请按[完整指南](docs/getting-started.zh-CN.md)操作。

## 模型部署流程

![模型准备、训练、导出、主机检查与烧录流程](docs/images/model-workflow.svg)

推荐工具位于 `tools/prepare`、`tools/training`、`tools/export` 和 `tools/validation`。早期训练方案保留在 `tools/experiments`，供研究和对照使用。

## 历史实验结果

以下数据来自 **v1.0.0 的实验记录**，并非每次提交都会重新测试的基准。实验过程见[开发记录](docs/development-notes.zh-CN.md)。

| 项目 | 配置或记录值 |
| --- | --- |
| 硬件 | 7 × ESP32-S3 N16R8；每板 16 MB Flash、8 MB PSRAM |
| 模型 | Qwen2-0.5B；24 层；词表裁剪至 32,000 |
| 训练 | WikiText-103；4,000 步；验证损失 4.58 / 困惑度 97.8 |
| 生成 | 端到端约 7 秒/token |
| 功耗 | 待机约 1.2 W；生成约 1.5 W |
| 长度限制 | 节点 KV 缓存 512 token；分词输入缓冲 256 token |

原始搭建中出现过回程链路数据损坏和首 token 长时间等待。训练结果、PC 输出或编译成功，均不能代替真实七板集群验证。

## 仓库结构

```text
firmware/             主板和计算节点的 ESP-IDF 工程
tools/                模型准备、训练、导出、验证与分析模块
scripts/              烧录、容器训练与仓库维护脚本
tests/                无需硬件的主机回归检查
docs/                 部署、架构、路径迁移及实验记录
  diagrams/           可编辑图源说明
  images/             文档使用的 SVG 图示
.github/              CI、Issue 和 Pull Request 模板
```

## 开发检查

```bash
uv sync --locked --extra analysis
uv run python -m unittest discover -s tests -v
uv run python scripts/check_repository.py
uv run python scripts/render_diagrams.py --check
```

主机测试、固件构建和硬件验证是不同层次的检查，贡献代码时应分别说明结果。参见[贡献指南](CONTRIBUTING.md)。

## 致谢与许可

本项目基于 [Low-Zi-Hong/ESP32s3-LLM-Cluster](https://github.com/Low-Zi-Hong/ESP32s3-LLM-Cluster) 的七板架构、固件基础与模型工具链，增加了乘加内核修复和激活量化感知训练流程。三值量化方法参考 [Microsoft BitNet](https://github.com/microsoft/BitNet)，基座模型来自 [Qwen2-0.5B](https://huggingface.co/Qwen/Qwen2-0.5B)。

仓库代码采用 [MIT 许可](LICENSE)，保留上游版权声明；模型权重与数据集遵循各自的上游许可。
