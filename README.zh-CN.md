<p align="center">
  <h1 align="center">ESP32-LLM-001</h1>
</p>

<p align="center">
  运行在七块 ESP32-S3 上的 1.58-bit 大语言模型流水线集群 ——<br>
  以每 token 约 7 秒的速度说英语，整机功耗不足 2 瓦。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

<p align="center">
  <a href="https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases/latest"><img src="https://img.shields.io/github/v/release/Crucifixion-Fxl/ESP32-LLM-001?display_name=tag" alt="最新发布"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT 许可">
  <img src="https://img.shields.io/badge/target-ESP32--S3%20N16R8-e7352b" alt="ESP32-S3 N16R8">
  <img src="https://img.shields.io/badge/model-Qwen2--0.5B%20%C2%B71.58--bit-615fff" alt="Qwen2-0.5B 1.58-bit">
  <img src="https://img.shields.io/badge/speed-~7%20s%20%2F%20token-0ea5e9" alt="每 token 约 7 秒">
</p>

<p align="center">
  <img src="docs/images/architecture.svg" alt="ESP32-LLM-001 集群架构：主板负责分词、词向量与采样；六个计算节点各运行四层 1.58-bit transformer，以三线 SPI 菊花链相连">
</p>

## 亮点

- 在七块约 ¥30 的微控制器开发板上运行真实的 0.5B 参数解码器
  （Qwen2-0.5B，词表裁剪至 32K），采用 **1.58-bit 三值权重** 与 INT4 词向量。
- 六个计算节点各执行四层 transformer——含 RoPE 注意力、PSRAM 中的分组查询
  KV Cache、SwiGLU MLP——通过三线 SPI 菊花链串联。
- 修复了上游固件中 **75% 权重从未参与推理** 的静默 bug（见下文）；重写了
  Xtensa EE 汇编乘加内核，以 64 项车道级单测验证，并固化为每次开机的自检。
- 训练即部署：per-vector int8 激活量化在 QAT 前向中被逐位模拟——
  GPU 上验证的算术，就是板子上执行的算术。
- `verify_int4_pc.py` 在 PC 上完整复现板子算术——烧录之前先过金标准。
- 完整工具链：支持断点续跑、早停与最优导出的训练脚本；macOS 一键烧录；
  以及一份从全新板子到开口说话约 40 分钟的复现手册（直接使用 Release 二进制）。

## 性能

| 指标 | 数值 |
| --- | --- |
| 模型 | Qwen2-0.5B → 32K 词表 → 1.58-bit 三值 + INT4 词向量 |
| 训练 | wikitext-103 · 4000 步 · **val loss 4.58 / PPL 97.8** |
| 推理 | 端到端 ~7 s/token · 单节点 4 层 1.04 s（55.6M 乘加）|
| 功耗 | 待机 ~1.2 W · 生成 ~1.5 W |
| 硬件成本 | 7 × ESP32-S3-N16R8 ≈ ¥210 + 杜邦线与面包板 ≈ ¥10 |
| 上下文 / 词表 | 512 token / 32K（16MB Flash 物理上限）|

实测输出（温度 0.4）：

```text
User > The capital of France is
Cluster > "...the largest ... city . ... in the 1980s ,
           the ... building is the ... highest known as the 2 0 0 0 0 0 0 0 0 ..."
```

PPL 98 + 温度采样的真实水平：语义孤岛裹着数字呓语。加练即变强，流水线不变。

## 快速开始

- **[docs/REPRODUCE.md](docs/REPRODUCE.md)** —— 零基础复现手册：材料清单、
  逐条命令、接线总表与故障排查目录。
- **[Releases](../../releases)** —— 可直接烧录的固件与模型二进制（v1.0.0），
  无需训练。

```bash
pip3 install esptool
# 主板（单独插这一块）
python3 -m esptool --chip esp32s3 --port PORT -b 921600 write_flash \
  0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 master_board.bin
python3 -m esptool --chip esp32s3 --port PORT -b 2000000 write_flash \
  0x90000 tokenizer.bin 0x150000 embed.bin 0xFF0000 final_norm.bin
# 随后六个节点各烧节点固件 + 对应的 layers_*.bin，接线、上电、115200 打开串口。
```

## 本仓库的核心贡献

**1. 修复汇编乘加内核中静默丢失 75% 权重的 bug。**
上游固件用连续四次 `ee.movi.32.q` 向同一个 Q 寄存器装配 `ee.vmulas.s8.accx`
的操作数。在 ESP32-S3 上，该指令是*整体覆写*语义（其余位清零），且乘加每次
只消耗低 32 位——于是四个权重字被抹掉三个，幸存者还与车道错位。不崩溃、
不报错，只有退化的输出。我们以脉冲扫描车道单测还原了有效置换
（σ(0)=12…σ(3)=15，车道 4–15 全灭），以"每寄存器一字、每组四发 vmulas"
重写内核，并把单测固化为开机自检。

**2. 让训练见到部署算术。**
固件在每次三值矩阵乘前将激活量化为 per-vector int8。上游 QAT 只量化权重，
GPU 侧验证无法预测板子行为。`tools/qat_speak.py` 在训练前向中逐位复刻
`quantize_X`（±127 截断、死区保护、STE 梯度）。

## 仓库结构

```text
├── README.md / README.zh-CN.md   # 项目主页（英文 / 简体中文）
├── docs/
│   ├── REPRODUCE.md              # 零基础复现手册
│   ├── JOURNEY.md                # 完整搭建与调试实录
│   └── images/                   # 示意图
├── firmware/
│   ├── master/                   # ESP-IDF 工程：分词 / 词向量 / LM Head / SPI
│   └── node/                     # ESP-IDF 工程：4 层 transformer 计算节点
│       └── main/bitlinear_forward_q.S   # 修复版汇编乘加内核
└── tools/
    ├── qat_speak.py              # 部署算术对齐 QAT（续跑 / 早停 / 最优导出）
    ├── verify_int4_pc.py         # PC 端板子算术金标准
    ├── flash_data.sh             # macOS 数据分区烧录
    ├── colab_prepare.py          # Colab 一键模型准备
    ├── deploy_4090.sh            # GPU 服务器部署助手
    └── crop_*.py, bit4_*.py, pack_*.py  # 上游量化与打包流水线
```

## 已知边界

- 首个 token 偶发停滞约 3 分钟后魔数校验失败——疑似 Node6→Master 回程段
  杜邦线虚接；Master 固件会打印坏帧原始字节辅助定位。
- 温度 0.4 下仍有复读倾向；可在 `firmware/master/main/main.cpp` 调整
  （`lm_head_sample(..., 0.4f)`）。
- 64 个 token 约 8 分钟——六跳串行流水线的真实成本。

## 致谢

- **[Low-Zi-Hong/ESP32s3-LLM-Cluster](https://github.com/Low-Zi-Hong/ESP32s3-LLM-Cluster)** ——
  本项目的架构基础：七板 SPI 菊花链设计、1.58-bit 固件骨架与 PC 端工具链
  均源于该仓库。本文所述的 ASM 修复与训练方法是在其基础上的增量工作。
- [microsoft/BitNet](https://github.com/microsoft/BitNet) —— 1.58-bit 三值量化思想。
- Qwen 团队 —— Qwen2-0.5B 基座模型。

## 许可

MIT（沿用上游）。Qwen2-0.5B 权重衍生品遵循其原始模型许可。
