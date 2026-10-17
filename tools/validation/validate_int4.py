from tools.paths import MODEL_DIR
# Decode firmware-format INT4 embeddings and ternary weights for a CPU smoke run.
# This does not emulate the Xtensa kernel or per-vector int8 activation quantization.
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from safetensors import safe_open

def unpack_158bit(packed_weight, gamma):
    out_features, packed_in_features = packed_weight.shape
    def decode(bits):
        val = torch.zeros_like(bits, dtype=torch.int8)
        val[bits == 1] = 1
        val[bits == 2] = -1
        return val
    w0 = decode((packed_weight)       & 0b11)
    w1 = decode((packed_weight >> 2)  & 0b11)
    w2 = decode((packed_weight >> 4)  & 0b11)
    w3 = decode((packed_weight >> 6)  & 0b11)
    ternary = torch.stack([w0, w1, w2, w3], dim=-1).view(out_features, -1).to(torch.float16)
    return ternary * gamma.to(torch.float16)

def unpack_4bit_emb_firmware(packed_weight, scales):
    """严格复刻 embedding.cpp：低4位→偶数列，高4位→奇数列，补码符号扩展"""
    vocab_size, packed_hidden = packed_weight.shape
    w0 = (packed_weight & 0x0F).to(torch.int8)
    w0 = torch.where(w0 >= 8, w0 - 16, w0)          # 补码符号扩展
    w1 = ((packed_weight >> 4) & 0x0F).to(torch.int8)
    w1 = torch.where(w1 >= 8, w1 - 16, w1)
    unpacked = torch.stack([w0, w1], dim=-1).view(vocab_size, -1).to(torch.float16)
    return unpacked * scales.to(torch.float16)

def main():
    model_path = str(MODEL_DIR)
    st_path = str(MODEL_DIR / "qwen_158_int4.safetensors")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16, device_map="cpu")

    with safe_open(st_path, framework="pt", device="cpu") as f:
        keys = f.keys()
        # 1) INT4 embedding（固件同款解码）
        packed_emb = f.get_tensor("model.embed_tokens.weight_packed_4bit")
        scales = f.get_tensor("model.embed_tokens.scales")
        emb = unpack_4bit_emb_firmware(packed_emb, scales)
        model.model.embed_tokens.weight.data.copy_(emb)
        model.lm_head.weight = model.model.embed_tokens.weight  # tie
        print(f"✅ INT4 词表已按固件解码方式挂载 ({tuple(emb.shape)})")
        # 2) 1.58-bit 层（与 run_model158 相同逻辑）
        n = 0
        for name, module in model.named_modules():
            pk, gk = f"{name}.weight_packed", f"{name}.gamma"
            if pk in keys:
                module.weight.data.copy_(unpack_158bit(f.get_tensor(pk), f.get_tensor(gk)))
                n += 1
            elif f"{name}.weight" in keys and "embed_tokens" not in name and "lm_head" not in name:
                module.weight.data.copy_(f.get_tensor(f"{name}.weight"))
        print(f"✅ {n} 个 1.58-bit 层已解包注入")

    model.eval()
    prompt = "in "
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=20, do_sample=False, temperature=None, top_p=None)
    print("PC+INT4(固件解码) 输出:", tokenizer.decode(out[0], skip_special_tokens=True))


if __name__ == "__main__":
    main()
