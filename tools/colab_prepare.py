# ============================================================
# Colab 准备单元格：在 Colab 里重建 cropped_Qwen（32K 裁剪模型）
# 用法：整段复制到 Colab 的一个单元格运行，约 5 分钟
# 依赖：无（先用 !pip install -q datasets 装好即可，本格只造模型）
# ============================================================
import os, json, subprocess, urllib.request

BASE = "/content/Qwen2-0.5B"          # 原始模型
OUT  = "/content/cropped_Qwen"        # 裁剪产物（qat_speak.py 的默认上级目录）
os.makedirs(BASE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# ---- 1. 下载原始模型的 4 个文件（Colab 网到 HF 很快）----
files = ["config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"]
for f in files:
    dst = os.path.join(BASE, f)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        print(f"跳过已有: {f}")
        continue
    url = f"https://huggingface.co/Qwen/Qwen2-0.5B/resolve/main/{f}"
    print(f"下载 {f} ...")
    urllib.request.urlretrieve(url, dst)
print("✅ 原始模型下载完成")

# ---- 2. 裁剪 tokenizer 到 32K（等价 crop_token.py）----
REGULAR_VOCAB_SIZE = 31990
SPECIAL_MAP = {"<|endoftext|>": 31997, "<|im_start|>": 31998, "<|im_end|>": 31999}

with open(f"{BASE}/tokenizer.json", encoding="utf-8") as f:
    data = json.load(f)

sorted_vocab = sorted(data["model"]["vocab"].items(), key=lambda x: x[1])
new_vocab = {}
for tok, _ in sorted_vocab:
    if tok in SPECIAL_MAP:
        continue
    new_vocab[tok] = len(new_vocab)
    if len(new_vocab) >= REGULAR_VOCAB_SIZE:
        break
for sp, new_id in SPECIAL_MAP.items():
    new_vocab[sp] = new_id

new_merges = [m for m in data["model"].get("merges", [])
              if all(p in new_vocab for p in m.split(" ")) and ("".join(m.split(" ")) in new_vocab)]
data["model"]["vocab"] = new_vocab
data["model"]["merges"] = new_merges

added = [{"id": new_id, "content": tok, "single_word": False, "lstrip": False,
          "rstrip": False, "normalized": False, "special": True}
         for tok, new_id in SPECIAL_MAP.items()]
data["added_tokens"] = added

with open(f"{OUT}/tokenizer.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

with open(f"{BASE}/tokenizer_config.json", encoding="utf-8") as f:
    tok_cfg = json.load(f)
tok_cfg["added_tokens_decoder"] = {str(a["id"]): a for a in added}
tok_cfg["bos_token"] = "<|endoftext|>"
tok_cfg["eos_token"] = "<|endoftext|>"
with open(f"{OUT}/tokenizer_config.json", "w", encoding="utf-8") as f:
    json.dump(tok_cfg, f, ensure_ascii=False, indent=2)

with open(f"{BASE}/config.json", encoding="utf-8") as f:
    config = json.load(f)
config["vocab_size"] = 32000
config["bos_token_id"] = 31997
config["eos_token_id"] = 31997
with open(f"{OUT}/config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print(f"✅ tokenizer 裁剪完成（vocab={len(new_vocab)}, merges={len(new_merges)}）")

# ---- 3. 裁剪 embedding 权重（等价 crop_model_weight.py）----
import torch
from safetensors.torch import load_file, save_file

state = load_file(f"{BASE}/model.safetensors")
old_embed = state["model.embed_tokens.weight"]
new_embed = old_embed[:32000, :].clone()
for old_id, new_id in {151643: 31997, 151644: 31998, 151645: 31999}.items():
    new_embed[new_id] = old_embed[old_id]
state["model.embed_tokens.weight"] = new_embed
state.pop("lm_head.weight", None)   # tie embedding，固件端复用
save_file(state, f"{OUT}/model.safetensors")
print(f"✅ 权重裁剪完成 {tuple(new_embed.shape)}")
print("\n🎉 准备完毕。接下来把 qat_speak.py 放到 /content 运行：")
print("   !python qat_speak.py --steps 1600")
print("   （qat_speak.py 默认 ../cropped_Qwen 相对路径；在 /content 下运行即命中 /content/cropped_Qwen）")
