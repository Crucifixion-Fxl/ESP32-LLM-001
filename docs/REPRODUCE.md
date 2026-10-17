# REPRODUCE.md —— 零基础复现手册

> 目标：任何人从一台干净的电脑开始，复现"7 块 ESP32-S3 跑 1.58-bit Qwen2-0.5B 集群"。
> 三条路径任选：
> - **路径 1（最快，~40 分钟）**：直接用本仓库 Release 里的固件+模型，跳过训练
> - **路径 2（完整，+1 小时 GPU）**：自己重新训练模型
> - **路径 3（极客，全源码）**：从 HuggingFace 原始模型开始全部自己来
>
> 配套阅读：[JOURNEY.md](JOURNEY.md)（原理与调试故事）

---

## 0. 成果与花费

你将得到：7 块 ESP32-S3 组成的流水线集群，跑 Qwen2-0.5B 的 1.58-bit 三值量化版，
~7 秒/token，可通过串口对话（PPL≈98 的"维基风呓语"水平）。

| 项目 | 花费 |
|---|---|
| ESP32-S3 开发板 ×7（必须 N16R8：16MB Flash + 8MB PSRAM）| ~¥30/块 ≈ ¥210 |
| USB 数据线 ×1-2（Type-C）| 已有 |
| 杜邦线（母母 ~30 根 + 公母 ~15 根）| ~¥10 |
| 面包板 ×1（只作共地/供电总线，板子不插上去）| ~¥5 |
| 实验台电源或多个 USB 充电头（5V，整机 <2W）| 已有 |
| （可选）LED + 电阻（接节点 GPIO8 观赏用）| ~¥1 |
| （路径 2）GPU：4090 约 1 小时 / Colab 免费约 3 小时 | ~¥0-5 |

---

## 1. 硬件准备

1. 检查板子丝印必须含 **N16R8**（16MB Flash + 8MB 八线 PSRAM，缺一不可：
   模型分区顶到 15.4MB，KV Cache 在 PSRAM）。
2. 给 7 块板贴标签：`Master`、`Node1(0-3)`、`Node2(4-7)`、`Node3(8-11)`、
   `Node4(12-15)`、`Node5(16-19)`、`Node6(20-23)`。
   **标签 = 物理链位 = 层数据文件，三者永远一致，这是本项目的第一铁律。**

---

## 2. 路径 1：用 Release 成品直接复现（推荐）

### 2.1 下载 Release

到 [Releases](https://github.com/Crucifixion-Fxl/ESP32-LLM-001/releases) 下载：

| 文件 | 内容 |
|---|---|
| `firmware-master.zip` | Master 固件（bootloader + 分区表 + app，已含温度 0.4 采样）|
| `firmware-node.zip` | 节点固件（已含 ASM 车道修复 + 开机自检）|
| `model-bins.zip` | tokenizer.bin + embed.bin + final_norm.bin + 6× layers_*.bin |

解压备用。

### 2.2 安装烧录工具（一次性）

```bash
# macOS（本手册主环境）
brew install python uv
uv init --bare 2>/dev/null; uv add esptool        # 或者: pip3 install esptool

# Windows: 安装 Python 后 pip install esptool
# Linux:   pip3 install esptool
```

### 2.3 烧录 Master（板子只插这一块）

```bash
ls /dev/cu.usbmodem*        # macOS 找串口；Windows 在设备管理器看 COMx

# ① 固件（zip 里三个文件按地址烧）
uv run python -m esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  write_flash 0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 master_board.bin

# ② 数据
uv run python -m esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 2000000 \
  write_flash 0x90000 tokenizer.bin 0x150000 embed.bin 0xFF0000 final_norm.bin
```

### 2.4 烧录 6 个节点（每次只插一块，按标签顺序）

```bash
# Node 1 —— 换插下一块前先把这行跑完
uv run python -m esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  write_flash 0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 node_board.bin
uv run python -m esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 2000000 \
  write_flash 0x90000 layers_0_to_3.bin

# Node 2 用 layers_4_to_7.bin，Node 3 用 layers_8_to_11.bin ……
# Node 6 用 layers_20_to_23.bin —— 文件名和标签一一对应，烧错不报错只出乱码！
```

> 报 `Failed to connect` → 按住板上 BOOT 键，短按一下 RST，松开 BOOT，重试。

烧完直接跳到 **第 4 节接线**。

---

## 3. 路径 2/3：自己训练（源码流水线）

### 3.1 电脑环境（macOS 示例）

```bash
brew install python uv git
git clone https://github.com/Crucifixion-Fxl/ESP32-LLM-001.git
cd ESP32-LLM-001

# Python 工具链
uv add torch transformers safetensors esptool accelerate datasets

# ESP-IDF（编译固件用，约 15 分钟）
mkdir -p ~/esp && cd ~/esp
git clone --depth 1 --branch v6.1-beta1 --recursive --shallow-submodules --jobs 8 \
  https://github.com/espressif/esp-idf.git
brew install python          # ESP-IDF 需要 python>=3.10，系统自带 3.9 不行
cd esp-idf && ./install.sh esp32s3
```

> 每次开新终端编译固件前：`. ~/esp/esp-idf/export.sh`

### 3.2 准备裁剪模型（在仓库根目录）

```bash
mkdir -p Qwen2-0.5B && cd Qwen2-0.5B
for f in config.json tokenizer.json tokenizer_config.json model.safetensors; do
  curl -L -O "https://huggingface.co/Qwen/Qwen2-0.5B/resolve/main/$f"
done
cd ../tools
python3 crop_token.py          # → ../cropped_Qwen/（32K 词表）
python3 crop_model_weight.py   # → ../cropped_Qwen/model.safetensors
```

### 3.3 训练（三处任选其一）

**A. 自有 NVIDIA GPU（推荐）**：

```bash
python qat_speak.py --steps 4000                # ~1h on 4090, val≈4.58/PPL≈98
# 继续加练：python qat_speak.py --resume --steps 50000   # 早停：10 轮验证无提升自动停
```

**B. Colab 免费**：上传 `tools/qat_speak.py` 和 `tools/colab_prepare.py`，
运行时选 T4/L4，依次执行：

```python
!pip install -q datasets
%run colab_prepare.py                # ~5 分钟，重建裁剪模型
!sed -i 's|\.\./cropped_Qwen|/content/cropped_Qwen|g' qat_speak.py
!python qat_speak.py --steps 4000
```

**C. 无 GPU**：直接用 Release 里的模型（路径 1）。

产物：`cropped_Qwen/qwen_158.safetensors`（~140MB）。

### 3.4 上板前金标准验证（强烈建议）

```bash
uv run python verify_int4_pc.py    # 先跑 bit4 再跑此步（见 3.5）
```

它会在 PC 上**完整模拟板子算术**（INT4 词向量 + 三值解包 + int8 激活量化）。
输出流利英语 → 板子上也流利；输出乱码 → 训练有问题，别浪费烧录时间。

### 3.5 打包 + 烧录

```bash
uv run python bit4_embedding.py     # embedding → INT4
uv run python pack_tokenizer_bin.py # tokenizer.bin
uv run python pack_model_bin.py     # bins/ 下 8 个烧录文件

# 编译固件
. ~/esp/esp-idf/export.sh
cd ../firmware/master && idf.py set-target esp32s3 && idf.py build && cd ../firmware/node && idf.py set-target esp32s3 && idf.py build && cd ..

# 烧录（同 2.3/2.4，固件改用 build/ 下的产物；数据用本仓库脚本）
cd tools
./flash_data.sh master /dev/cu.usbmodemXXXX
./flash_data.sh node   /dev/cu.usbmodemXXXX layers_0_to_3.bin   # 每节点换文件名
```

---

## 4. 接线（先烧完再接！烧录时 RST 链必须断开）

板子一字排开：`[Master] [N1] [N2] [N3] [N4] [N5] [N6]`

### 4.1 共地（第一优先级）

每块板任意 GND → 面包板**蓝轨**（7 根公母线，全插轨的同一半）。

### 4.2 SPI 菊花链（7 段 × 3 根母母线，口诀 4→15、5→16、7→18）

| # | 上游板 GPIO 4/5/7 | 下游板 GPIO 15/16/18 |
|---|---|---|
| 1 | Master | Node 1 |
| 2 | Node 1 | Node 2 |
| 3 | Node 2 | Node 3 |
| 4 | Node 3 | Node 4 |
| 5 | Node 4 | Node 5 |
| 6 | Node 5 | Node 6 |
| 7 | **Node 6** | **Master**（回程段，最容易漏！）|

### 4.3 复位级联（6 根母母线）

`每块板 GPIO 1 → 下一块板的 EN(RST) 引脚`；Node 6 的 GPIO 1 悬空。
（级联开机：Master 复位 N1，N1 复位 N2……N6 就绪 = 全链就绪）

### 4.4 就绪回环（1 根）

`Node 6 GPIO 3 → Master GPIO 3`

### 4.5 供电

- 节点 1-6：5V 引脚 → 面包板红轨 ← 实验台电源（5.0V / 限流 1A）
- Master：电脑 USB（它是你的对话终端）
- **共地注意**：电源负极必须进蓝轨；节点用 DC 供电时不要再插 USB

### 4.6 上电前自查（90% 事故就这三条）

1. 段 7（Node6→Master）接了吗？
2. SPI 三根线有没有交叉（必须 4→15、5→16、7→18 一一对应）？
3. 复位链方向对吗（GPIO1 → **下一块** 的 EN）？N6 的 GPIO1 是不是悬空？

---

## 5. 上电与对话

1. 开节点电源（表头 ~0.2A = 6 板正常开机，LED 按链序闪一波）
2. Master 插电脑 USB（Mac 弹"无法识别的键盘"→ 忽略）
3. 连串口（115200）：

```bash
# macOS
screen /dev/cu.usbmodemXXXX 115200     # 或: idf.py -p PORT monitor（ESP-IDF 环境）
```

4. 看到 `ALL NODE READY!!!` 和 `>>> Qwen 1.58-bit MCU Cluster Ready` 即成功
5. 输入一句话回车，等 ~8 分钟（64 token × ~7s）：

```
User > The capital of France is
Assitant > ...the largest ... city ... in the 1980s ...
```

6. `/bench` + 回车可切换基准测试模式（下次生成结束打印耗时/吞吐报告）

---

## 6. 故障排查表（我们踩过的每一个坑）

| 症状 | 原因 | 解法 |
|---|---|---|
| 找不到 `token`/`model` 分区 | 没开自定义分区表 | 用本仓库 `sdkconfig.defaults` 重新编译 |
| 板子运行正常但串口无输出 | 控制台在 UART0 引脚而非 USB | `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`（已含在 defaults）|
| 烧录 `Failed to connect` | 下载模式没进 / RST 链接着 | 断开 GPIO1→EN 连线；或 BOOT+RST 手动进 |
| 输出乱码/复读单个词 | 层数据烧错链位 / 训练不足 | 核对标签↔文件名；PC 跑 verify_int4_pc.py 定位 |
| `Node 加载超时`，横幅不出 | 某节点没上电或复位链断 | 看电流表哪块板没启动；查 GPIO1→EN 链 |
| 首帧卡 ~3 分钟后报魔数错 | 接线虚接（多在回程段）| 按实 N6→Master 三根线 + 共地；重插 USB 复位全链 |
| 输出全是 `@",!"` 类标点 | 在跑未训练的 demo 权重 | 用 Release 模型或按路径 2 训练 |
| 电流表 0A | 母头杜邦线插不进面包板 | 板子↔面包板必须用**公母**线 |
| 训练 loss 不降 | 没加载训练后 bias 等 | 用本仓库 qat_speak.py，勿混用上游脚本 |

---

## 7. 常用修改

| 想要 | 改哪里 | 然后 |
|---|---|---|
| 换个回答风格 | `firmware/master/main/main.cpp` 里 `lm_head_sample(..., 0.4f)` 改温度（0=贪心复读，1+放飞）| 重编译重烧 Master 固件 |
| 生成更长 | 同文件 `MAX_GEN_LEN 64` → 128 | 同上（每 token 约 7s，量力而行）|
| 换个引脚布局 | `*/main/spi_bus.h` 顶部的宏 | 重编译全部固件 |
| 更聪明的模型 | `qat_speak.py --resume --steps 50000` 加练 | 重跑 3.5 打包烧录 |

---

## 8. 性能与极限

- 单节点：4 层 55.6M 乘加 / 1.04s（双核 + EE 向量指令 + 三值 LUT）
- 全链 ~7s/token（6 节点串行转运 + Master 头尾开销）
- 功耗：待机 ~1.2W，推理 ~1.5W
- 上下文 512 token，词表 32K（16MB Flash 的硬上限）
- 扩容：每加 4 层加一块节点板（改 `pack_model_bin.py` 的切分与分区表）
