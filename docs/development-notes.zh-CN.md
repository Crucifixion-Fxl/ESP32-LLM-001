> 历史记录：以下保留 v1.0.0 实验时的命令、文件名和观察。当前可执行步骤以[复现指南](getting-started.zh-CN.md)为准，旧路径参见[迁移表](repository-layout.md)。其中“金标准/完整模拟”是当时的表述；PC 工具实际只验证权重解码与生成，不完整模拟固件 INT8 激活和 Xtensa 运算。64 项启动诊断目前仅打印比较值，不自动断言通过。

# ESP32-LLM-001 复刻之旅：从 git clone 到会说话的 7 板集群

> 2026-10-17，一天完成。基于 [Low-Zi-Hong/ESP32s3-LLM-Cluster](https://github.com/Low-Zi-Hong/ESP32s3-LLM-Cluster) 复刻并深度修复。
> 本仓库包含复刻过程中发现并修复的 **2 个上游 Bug**（其一为静默权重丢失）、**1 套部署算术对齐的训练方法**、以及完整的一手调试记录。

## 最终成果

| 指标 | 数值 |
|---|---|
| 硬件 | 7 × ESP32-S3 N16R8（16MB Flash + 8MB 八线 PSRAM）|
| 模型 | Qwen2-0.5B → 32K 词表裁剪 → 1.58-bit 三值权重 + INT4 词向量 |
| 训练 | wikitext-103, 4000 步（含部署算术预演）: **val loss 4.58 / PPL 97.8** |
| 速度 | 修复版 ASM：**1.04 s/节点/4 层**，全链 ~7 s/token |
| 采样 | 温度 0.4（固件原生支持，破除贪心复读）|

实拍输出（`The capital of France is` →）：

```
"...the largest largest largest largest largest city . The largest number is
1 1 @ . @ 1 0 % in the 1 9 8 0 s , the largest building is the highest known
as the 2 0 0 0 0 0 0 0 0 0 0 ."
```

PPL 98 的小模型 + 温度采样的真实水平：语义孤岛（city、1980s）+ 数字呓语。

---

## 一、部署流水线（PC 端）

```
Qwen2-0.5B (HF)
  ├─ crop_token.py          151K → 32K 词表（特殊 token 固定 31997-31999）
  ├─ crop_model_weight.py   embedding 矩阵裁剪 + 特殊 token 向量搬运 + 删 lm_head
  ├─ qat_speak.py           ★本仓库新增：见下文
  ├─ bit4_embedding.py      embedding FP16 → INT4（逐行 scale）
  ├─ pack_tokenizer_bin.py  tokenizer → ESP32 mmap 格式
  └─ pack_model_bin.py      按固件 advance() 字节序切 6 段层文件 + embed + fnorm
```

烧录（macOS，本仓库新增 `flash_data.sh`）：

```
Master: 固件 + tokenizer@0x90000 + embed@0x150000 + fnorm@0xFF0000
Node i: 固件 + layers_(4i)_to_(4i+3).bin@0x90000   # 物理链位必须与层范围一致
```

## 二、★ qat_speak.py：让训练见到板子上的真实算术

上游的训练脚本只对**权重**做三值 QAT，而固件在推理时还会把**激活值**量化成 int8
（`quantize_X`: per-vector 对称，scale=max|x|/127, round+clamp±127）。训练算术 ≠
部署算术，脆模型上板即崩——这是"PC 模拟流利、板子输出乱码"的核心原因之一。

`qat_speak.py` 在 `BitNetLinear.forward` 中逐位复刻固件算术：

```python
def firmware_fake_quant_x(x):
    max_val = x.abs().amax(dim=-1, keepdim=True)
    dead = max_val < 1e-5                       # 固件的死区保护
    scale = torch.where(dead, 1, max_val) / 127.0
    q = torch.clamp(torch.round(x / scale), -127.0, 127.0)
    return torch.where(dead, 0, q * scale)      # STE 直通回传
```

其他增强：wikitext-103、断点续跑（`--resume`）、早停（连续 N 轮验证无提升）、
**只导出历史最优权重**、硬件自适应（CUDA bf16/fp16、MPS、CPU）。

训练演进（RTX 4090）：

| 轮次 | 步数 | val loss | PPL | 备注 |
|---|---|---|---|---|
| demo（上游脚本）| 150 | ~8 | 乱码 | 单句过拟合 |
| 第 1 轮 | 1600 | 4.86 | 129 | Colab 弃用后转 4090 |
| 第 2 轮 | 4000 | 4.58 | 98 | 续训 |
| 马拉松 | 50000 上限 + 早停 | — | — | `--steps 50000 --patience 10` |

## 三、破案 1：编码一致性判别实验链

现象：同一份权重，PC 模拟器流利，板上乱码。逐一控制变量：

```
PC + FP16 词向量          → 复现训练句 ✓
PC + 固件同款 INT4 解码    → 复现训练句 ✓   （排除打包/编码 bug）
板子（INT4 + 三值）        → 排名 1018 的词 ✗
```

锁定差异 = 固件的 **int8 激活量化路径**（`quantize_X` + `bitlinear_forward_q`）。
解法即上文"训练预演部署算术"。验证工具 `verify_int4_pc.py` 可在 PC 上完整模拟
板子算术（INT4 词向量 + 三值解包 + 激活假量化），上板前的金标准。

## 四、破案 2：ASM 车道 bug（上游固件静默丢失 75% 权重）

部署算术对齐后板子输出仍是"词级碎片复读"。三步定位：

**① 双路径对决**（同输入分别跑 ASM 路径与纯 C++ 参考路径）：

```
C++ 路径 == PC 参考（逐位一致）→ 数据/权重/布局/算法全部无罪
ASM 路径 ≠ 两者               → 病灶在 bitlinear_forward_q 的汇编/调度
```

**② 车道级脉冲单测**（`asm_lane_unit_test`，已固化进固件开机自检）：
构造已知 2-bit 码型权重行，x 只在一个车道放 127，扫 16 车道 × 4 组二进制码型，
从 ASM 返回值还原有效置换 σ：

```
σ(0)=12, σ(1)=13, σ(2)=14, σ(3)=15   ← 车道 0-3 读的是槽 12-15！
车道 4-15 恒返回 0                    ← 75% 的乘加从未发生！
```

**③ 实锤 ISA 语义**（与 ESP32-S3 EE 扩展指令的两条事实吻合）：

- `ee.movi.32.q q, ar, imm` 是**整体覆写**：q = ar 放到 `(3-imm)*32` 位、其余清零。
  上游固件连续四次写同一个 q1 → 互相清零，只有最后一个字（byte3）幸存；
- `ee.vmulas.s8.accx qa, qb` 每次只消耗寄存器**低 32 位**（4 车道）。

上游代码（错误示范）：

```asm
ee.movi.32.q q1, a6, 0    # ← 每条指令都把 q1 整体替换！
ee.movi.32.q q1, a7, 1    # ← a6 已被清掉
ee.movi.32.q q1, a8, 2
ee.movi.32.q q1, a9, 3    # ← 只剩 a9 活着，还和车道 0-3 错位配对
ee.vmulas.s8.accx q0, q1  # ← 只算了 4/16 车道
```

修复习语（`firmware/node/main/bitlinear_forward_q.S`）：8 个 Q 寄存器各装一个
32 位字（movi 的覆写特性反而成为优点，imm=3 恰好落在 vmulas 消耗的低 32 位），
打 4 发 vmulas：

```asm
ee.movi.32.q q0, a6, 3    # x[0..3]
ee.movi.32.q q1, a7, 3    # x[4..7]
ee.movi.32.q q2, a8, 3
ee.movi.32.q q3, a9, 3
# ... LUT 解包 4 个权重字到 q4..q7（同样 imm=3）
ee.vmulas.s8.accx q0, q4
ee.vmulas.s8.accx q1, q5
ee.vmulas.s8.accx q2, q6
ee.vmulas.s8.accx q3, q7
```

修复后 64/64 车道单测全过，实测 **1.04 s/节点/4 层**（55.6M 乘加）。
注：上游 README 宣称的 1.3 s/节点是**少算 75% 工作量时**的速度。

> 附注：上游浮点版 `bitlinear_forward.S` 也有类似隐患——作者自己都用"存回内存
> + 标量 FPU 累加"兜底，从未使用向量 MAC。

## 五、ESP-IDF 踩坑记录（sdkconfig.defaults 已修）

1. **自定义分区表不生效**：项目根目录放 `partitions.csv` 不会自动被使用，
   必须 `CONFIG_PARTITION_TABLE_CUSTOM=y`，否则烧的是默认表（token/model/fnorm
   分区不存在，运行时报 `cannot find 'token' partition`）。
2. **USB 控制台**：N16R8 板 USB 直连芯片 USB-Serial-JTAG，但 ESP-IDF 默认把日志
   打到 UART0 引脚（GPIO43/44），USB 口一片寂静。需要
   `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`。
3. 烧录时若报 `Failed to connect`：按住 BOOT 再点一下 RST。

## 六、硬件接线（摘录）

```
SPI 菊花链（每段 3 线）: 上游 GPIO4/5/7 → 下游 GPIO15/16/18
                          共 7 段（Master→N1...N5→N6→Master 回程）
复位级联: 每板 GPIO1 → 下游 EN/RST；N6 的 GPIO1 悬空
就绪回环: N6 GPIO3 → Master GPIO3（级联启动完毕的信号）
共地: 7 板 GND 并到面包板蓝轨；实验台电源 5V/限流 1A 红轨供节点
```

排查利器：节点固件开机自跑 `asm_lane_unit_test`（64 项车道单测）；Master 的
`spi_bus.cpp` 带坏帧原始字节打印（`SPI 魔数错误! ... Raw Header Hex`）。

## 七、已知问题

- **首帧偶发停摆**：上电后第一个 token 偶发 ~3 分钟后坏魔数（疑似接线虚接，
  动一动线常自愈；复发先查 N6→Master 回程三根线）。
- **复读倾向**：PPL~98 + 温度 0.4 下仍有话题词复读。可调
  `firmware/master/main/main.cpp` 中 `lm_head_sample(..., 0.4f)`。
- 生成 64 token ≈ 8 分钟（~7 s/token 为全链串行转运的真实成本）。

## 八、本仓库相对上游的变更清单

```
新增  tools/qat_speak.py        部署算术对齐训练 + 早停 + 最优导出
新增  tools/verify_int4_pc.py   PC 端板子算术金标准验证
新增  tools/colab_prepare.py    Colab 一键重建裁剪模型
新增  tools/deploy_4090.sh      4090 服务器部署脚本
新增  tools/flash_data.sh       macOS 数据分区烧录（替代 .bat）
新增  firmware/master/sdkconfig.defaults  16MB Flash + 八线 PSRAM + USB 控制台 + 自定义分区表
新增  firmware/node/sdkconfig.defaults    同上
修复  firmware/node/main/bitlinear_forward_q.S   ★ movi/vmulas 车道 bug（75% 权重丢失）
修改  firmware/node/main/main.cpp         开机 64 项车道自检 asm_lane_unit_test
修改  firmware/node/main/bitlinear.h/cpp  bitlinear_forward_q_cpp 金标准声明
修改  firmware/master/main/main.cpp       MAX_GEN_LEN=64、温度 0.4、隐状态调试打印
修改  firmware/master/main/spi_bus.cpp    坏帧验尸打印
```

## 致谢

- [Low-Zi-Hong/ESP32s3-LLM-Cluster](https://github.com/Low-Zi-Hong/ESP32s3-LLM-Cluster) —— 架构与全部基础代码
- [microsoft/BitNet](https://github.com/microsoft/BitNet) —— 1.58-bit 量化思想
- Qwen 团队 —— Qwen2-0.5B 基座

MIT License 沿用上游。
