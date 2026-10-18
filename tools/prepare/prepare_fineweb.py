"""
prepare_fineweb.py —— 为 qat_speak.py 制备 fineweb 训练语料
================================================================
流式下载 HuggingFaceFW/fineweb (sample-10BT)，用裁剪后的 32K 词表分词，
切成 512-token 定长块，train/validation 分割后 save_to_disk。

产物: /ws/esp32-llm/fineweb_512 （供 qat_speak.py --data 使用）

用法: python3 prepare_fineweb.py [--docs 120000]
"""
import argparse
import os

import torch
from transformers import AutoTokenizer
from datasets import load_dataset, DatasetDict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.paths import MODEL_DIR

OUT_DIR = str(MODEL_DIR.parent / "fineweb_512")
BLOCK = 512


def group_texts(input_ids_list):
    """拼接所有 token，切 512 块，labels = input_ids（自回归）"""
    concat = []
    for ids in input_ids_list:
        concat.extend(ids)
    total = (len(concat) // BLOCK) * BLOCK
    blocks = []
    for i in range(0, total, BLOCK):
        chunk = concat[i:i + BLOCK]
        blocks.append({
            "input_ids": chunk,
            "attention_mask": [1] * BLOCK,
            "labels": list(chunk),
        })
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=120000, help="number of documents to keep (after filtering)")
    ap.add_argument("--out", default=OUT_DIR, help="output dataset directory")
    ap.add_argument("--min-chars", type=int, default=200)
    ap.add_argument("--val-frac", type=float, default=0.01)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(MODEL_DIR)

    print("🌐 流式加载 fineweb sample-10BT ...")
    stream = load_dataset("HuggingFaceFW/fineweb", "sample-10BT",
                          split="train", streaming=True)

    kept = 0
    batch_texts = []
    all_ids = []
    for doc in stream:
        text = doc.get("text", "")
        if len(text) < args.min_chars:
            continue
        batch_texts.append(text)
        kept += 1
        if len(batch_texts) >= 1000:
            enc = tok(batch_texts, add_special_tokens=False)["input_ids"]
            all_ids.extend(enc)
            batch_texts = []
            if kept % 10000 == 0:
                print(f"  已取 {kept}/{args.docs} 文档, 累计 {sum(len(x) for x in all_ids)/1e6:.0f}M tokens", flush=True)
        if kept >= args.docs:
            break
    if batch_texts:
        all_ids.extend(tok(batch_texts, add_special_tokens=False)["input_ids"])

    total_tokens = sum(len(x) for x in all_ids)
    print(f"✅ 取样完成: {kept} 文档 / {total_tokens/1e6:.0f}M tokens，开始分组 ...")

    blocks = group_texts(all_ids)
    n_val = max(64, int(len(blocks) * args.val_frac))
    n_train = len(blocks) - n_val
    print(f"📦 {len(blocks)} 个 512-token 块 → train {n_train} / val {n_val}")

    import random
    random.seed(42)
    random.shuffle(blocks)

    cols = {"input_ids": [b["input_ids"] for b in blocks],
            "attention_mask": [b["attention_mask"] for b in blocks],
            "labels": [b["labels"] for b in blocks]}
    from datasets import Dataset
    full = Dataset.from_dict(cols)
    ds = DatasetDict({
        "train": full.select(range(n_train)),
        "validation": full.select(range(n_train, len(blocks))),
    })
    OUT_DIR = args.out
    ds.save_to_disk(OUT_DIR)
    print(f"dataset saved to {OUT_DIR}")
    print(f"下一步: python3 qat_speak.py --from-best --data {OUT_DIR} --steps 8000 "
          f"--ckpt ckpt_fineweb --export-path /ws/esp32-llm/cropped_Qwen/qwen_158_fineweb.safetensors")


if __name__ == "__main__":
    main()
