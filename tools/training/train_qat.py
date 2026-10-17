"""
train_qat.py — 让 ESP32 集群"真说话"的 QAT 训练脚本
=====================================================
相比原版 train_qat_weights_only.py 的三个升级：
1. 激活量化对齐固件：逐位复刻 node_board bitlinear.cpp 的 quantize_X
   (per-vector 对称 int8, scale = max|x|/127, round + clamp ±127)，
   训练时模型就见过板子上的真实算术，不再出现"PC 好、板子废"的脆断
2. 数据升级：wikitext-2 → wikitext-103（约 500MB，流畅度质变）
3. 断点续跑：--resume（Colab 免费会话随时可能断，断了重跑即可接着练）

用法：
  python -m tools.training.train_qat --steps 1600          # 从头训
  python -m tools.training.train_qat --resume              # 断点续跑
产物：cropped_Qwen/qwen_158.safetensors（与现有打包/烧录流水线完全兼容）

硬件自适应：CUDA bf16（A 卡以上）/ CUDA fp16+GradScaler（T4 等）/
           Mac MPS / 纯 CPU（慢，仅应急）
"""
from tools.paths import MODEL_DIR
import os
import sys
import argparse
import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

# ============================================================
# 1. QAT 算子：权重三值 STE + 激活 int8 假量化（对齐固件 quantize_X）
# ============================================================
class BitNet158STE(torch.autograd.Function):
    """权重 {-1,0,1} 三值化，直通估计器回传梯度（与 train_qat_weights_only.py 一致）"""
    @staticmethod
    def forward(ctx, weight):
        eps = 1e-8
        gamma = weight.abs().mean()
        weight_scaled = weight / (gamma + eps)
        weight_clip = torch.clamp(torch.round(weight_scaled), -1.0, 1.0)
        ctx.save_for_backward(weight_scaled)
        return weight_clip * gamma

    @staticmethod
    def backward(ctx, grad_output):
        (weight_scaled,) = ctx.saved_tensors
        grad_weight = grad_output.clone()
        grad_weight[weight_scaled > 1.0] = 0.0
        grad_weight[weight_scaled < -1.0] = 0.0
        return grad_weight


def firmware_fake_quant_x(x: torch.Tensor) -> torch.Tensor:
    """复刻 bitlinear.cpp quantize_X：沿最后一维（hidden）逐向量对称 int8。

    固件逻辑：scale = max|x|/127; q = clamp(round(x/scale), -127, 127)
    反向用直通（round 的梯度当恒等），clamp 出界梯度为 0——标准 QAT 姿势。
    """
    max_val = x.abs().amax(dim=-1, keepdim=True)
    # 固件对近零向量直接置 0
    dead = max_val < 1e-5
    max_safe = torch.where(dead, torch.ones_like(max_val), max_val)
    scale = max_safe / 127.0
    q = torch.clamp(torch.round(x / scale), -127.0, 127.0)
    deq = q * scale
    return torch.where(dead, torch.zeros_like(deq), deq)


class BitNetLinear(nn.Linear):
    """部署算术的"预演"层：y = linear(fake_quant(x), ternary(w))"""
    def __init__(self, in_features, out_features, bias=True):
        super().__init__(in_features, out_features, bias=bias)

    def forward(self, x):
        w_quant = BitNet158STE.apply(self.weight)
        x_hat = firmware_fake_quant_x(x)
        return F.linear(x_hat, w_quant, self.bias)


def replace_linear_with_bitnet(model, target_modules=None):
    if target_modules is None:
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"]
    count = 0
    for name, module in model.named_children():
        if isinstance(module, nn.Linear) and any(t in name for t in target_modules):
            new_module = BitNetLinear(module.in_features, module.out_features,
                                      bias=module.bias is not None)
            new_module.weight.data = module.weight.data.clone()
            if module.bias is not None:
                new_module.bias.data = module.bias.data.clone()
            setattr(model, name, new_module)
            count += 1
        else:
            count += replace_linear_with_bitnet(module, target_modules)
    return count

# ============================================================
# 2. 导出（与 train_qat_weights_only.py / 固件解码端完全一致的打包格式）
# ============================================================
def export_158bit_safetensors(model, export_path):
    from safetensors.torch import save_file
    model.eval()
    export_dict = {}
    pack_multiplier = torch.tensor([1, 4, 16, 64], dtype=torch.uint8, device="cpu")

    print("\n📦 提取与打包模型权重...")
    with torch.no_grad():
        for name, module in model.named_modules():
            if isinstance(module, BitNetLinear):
                weight = module.weight.data.cpu()
                gamma = weight.abs().mean()
                weight_scaled = weight / (gamma + 1e-8)
                weight_ternary = torch.clamp(torch.round(weight_scaled), -1.0, 1.0)

                weight_mapped = torch.zeros_like(weight_ternary, dtype=torch.uint8)
                weight_mapped[weight_ternary == 1] = 1   # 1  -> 0b01
                weight_mapped[weight_ternary == -1] = 2  # -1 -> 0b10

                out_features, in_features = weight_mapped.shape
                assert in_features % 4 == 0

                reshaped = weight_mapped.view(out_features, in_features // 4, 4)
                packed = (reshaped * pack_multiplier).sum(dim=-1).to(torch.uint8)

                export_dict[f"{name}.weight_packed"] = packed
                export_dict[f"{name}.gamma"] = gamma.to(torch.float16)
                if module.bias is not None:
                    export_dict[f"{name}.bias"] = module.bias.data.cpu().to(torch.float16)

            elif "norm" in module.__class__.__name__.lower() and getattr(module, "weight", None) is not None:
                export_dict[f"{name}.weight"] = module.weight.data.cpu().to(torch.float16)

            elif isinstance(module, nn.Embedding):
                export_dict[f"{name}.weight"] = module.weight.data.cpu().to(torch.float16)

    os.makedirs(os.path.dirname(os.path.abspath(export_path)), exist_ok=True)
    save_file(export_dict, export_path)
    print(f"🎉 导出完成: {export_path}（{len(export_dict)} 个张量）")

# ============================================================
# 3. 数据：wikitext-103 → 512-token 定长块
# ============================================================
def build_dataloaders(tokenizer, block_size=512, batch_size=1):
    from datasets import load_dataset

    print("📚 加载 wikitext-103-raw-v1 ...")
    ds = load_dataset("Salesforce/wikitext", "wikitext-103-raw-v1")

    def tokenize_fn(examples):
        return tokenizer(examples["text"])

    def group_texts(examples):
        concatenated = {k: sum(examples[k], []) for k in examples.keys()}
        total_len = len(concatenated[list(concatenated.keys())[0]])
        total_len = (total_len // block_size) * block_size
        result = {k: [t[i:i + block_size] for i in range(0, total_len, block_size)]
                  for k, t in concatenated.items()}
        result["labels"] = result["input_ids"].copy()
        return result

    loaders = {}
    for split, shuffle in (("train", True), ("validation", False)):
        data = ds[split].filter(lambda x: len(x["text"].strip()) > 0, num_proc=4)
        tokenized = data.map(tokenize_fn, batched=True, remove_columns=["text"],
                             desc=f"Tokenizing {split}")
        grouped = tokenized.map(group_texts, batched=True, desc=f"Grouping {split}")
        grouped.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
        loaders[split] = DataLoader(grouped, batch_size=batch_size, shuffle=shuffle,
                                    pin_memory=True, num_workers=0, drop_last=True)
    return loaders["train"], loaders["validation"]

# ============================================================
# 4. 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Train deployment-aligned ternary QAT weights.")
    default_model = str(MODEL_DIR)
    parser.add_argument("--model-dir", default=default_model)
    parser.add_argument("--export-path",
                        default=os.path.join(default_model, "qwen_158.safetensors"))
    parser.add_argument("--steps", type=int, default=1600)
    parser.add_argument("--accum", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--eval-every", type=int, default=200)
    parser.add_argument("--patience", type=int, default=10, help="连续 N 轮验证无提升则早停")
    parser.add_argument("--ckpt", default=str(MODEL_DIR.parent / "checkpoints" / "qat"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--amp", choices=["auto", "bf16", "fp16", "fp32"], default="auto")
    args = parser.parse_args()

    # ---------- 设备与精度 ----------
    if torch.cuda.is_available():
        device = "cuda"
        if args.amp == "auto":
            amp_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            amp_dtype = {"bf16": torch.bfloat16, "fp16": torch.float16,
                         "fp32": None, "auto": None}[args.amp]
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device, amp_dtype = "mps", None          # MPS 上走 fp32 最稳
    else:
        device, amp_dtype = "cpu", None
    use_scaler = (device == "cuda" and amp_dtype == torch.float16)
    print(f"🚀 设备: {device} | 混合精度: {amp_dtype} | GradScaler: {use_scaler}")

    from transformers import AutoTokenizer, AutoModelForCausalLM, get_cosine_schedule_with_warmup

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    # torch_dtype: 新老 transformers 通吃（新版仅警告不报错）
    model = AutoModelForCausalLM.from_pretrained(args.model_dir, torch_dtype=torch.float32)
    model.gradient_checkpointing_enable()

    n = replace_linear_with_bitnet(model)
    print(f"✅ 已替换 {n} 个线性层为 BitNetLinear（含激活 int8 假量化）")
    model.to(device).train()

    train_loader, val_loader = build_dataloaders(tokenizer, args.block_size, args.batch_size)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = get_cosine_schedule_with_warmup(optimizer, args.warmup, args.steps)
    scaler = torch.amp.GradScaler("cuda", enabled=use_scaler)

    # ---------- 断点续跑 ----------
    os.makedirs(args.ckpt, exist_ok=True)
    ckpt_path = os.path.join(args.ckpt, "latest.pt")
    start_step, best_val, stall = 0, math.inf, 0
    if args.resume and os.path.exists(ckpt_path):
        state = torch.load(ckpt_path, map_location=device)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
        start_step, best_val = state["step"], state.get("best_val", math.inf)
        print(f"↩️ 从第 {start_step} 步恢复")

    def autocast_ctx():
        return torch.autocast(device_type=device, dtype=amp_dtype) if amp_dtype else torch.autocast(device_type="cpu", enabled=False)

    # ---------- 验证 ----------
    def evaluate(max_batches=30):
        model.eval()
        total, count = 0.0, 0
        with torch.no_grad():
            for i, batch in enumerate(val_loader):
                if i >= max_batches:
                    break
                ids = batch["input_ids"].to(device)
                with autocast_ctx():
                    loss = model(input_ids=ids, labels=ids.clone()).loss
                total += loss.item()
                count += 1
        model.train()
        return total / max(count, 1)

    # ---------- 训练循环 ----------
    print(f"\n🔥 开始 QAT：目标 {args.steps} 步（有效 batch = {args.batch_size * args.accum}）")
    step, micro, accum_loss = start_step, 0, 0.0
    done = False

    while not done:
        for batch in train_loader:
            if step >= args.steps:
                done = True
                break
            ids = batch["input_ids"].to(device, non_blocking=True)

            with autocast_ctx():
                loss = model(input_ids=ids, labels=ids.clone()).loss / args.accum
            scaler.scale(loss).backward()
            accum_loss += loss.item()
            micro += 1

            if micro % args.accum == 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()
                step += 1

                if step % 20 == 0:
                    # accum_loss 已是 4 个微批的平均，直接显示
                    print(f"step {step}/{args.steps} | loss {accum_loss:.4f} "
                          f"| lr {scheduler.get_last_lr()[0]:.2e}", flush=True)
                accum_loss = 0.0

                if step % args.eval_every == 0:
                    val = evaluate()
                    if val < best_val:
                        best_val = val
                        torch.save(model.state_dict(), os.path.join(args.ckpt, "best.pt"))
                        print(f"📍 step {step} | val loss {val:.4f} | PPL {math.exp(val):.1f} ★已存最优",
                              flush=True)
                        stall = 0
                    else:
                        stall += 1
                        print(f"📍 step {step} | val loss {val:.4f} | PPL {math.exp(val):.1f} (停滞 {stall}/{args.patience})",
                              flush=True)
                        if stall >= args.patience:
                            print(f"🛑 早停：连续 {args.patience} 轮无提升", flush=True)
                            done = True
                            break

                if step % 200 == 0 or step == args.steps:
                    torch.save({"model": model.state_dict(),
                                "optimizer": optimizer.state_dict(),
                                "scheduler": scheduler.state_dict(),
                                "scaler": scaler.state_dict(),
                                "step": step, "best_val": best_val}, ckpt_path)

    print("\n✅ 训练结束")
    best_path = os.path.join(args.ckpt, "best.pt")
    if os.path.exists(best_path):
        print("🏆 加载历史最优权重进行导出...")
        model.load_state_dict(torch.load(best_path, map_location=device))
    export_158bit_safetensors(model, args.export_path)

    # Colab 上的收尾提示
    if os.path.exists("/content"):
        print("\n" + "=" * 60)
        print("在 Colab 里下载产物（任选其一）：")
        print("  from google.colab import files")
        print(f"  files.download('{os.path.abspath(args.export_path)}')")
        print("或挂载 Google Drive 后 copy 过去，稍后取回")


if __name__ == "__main__":
    main()
