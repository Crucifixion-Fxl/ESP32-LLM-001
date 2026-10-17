from tools.paths import MODEL_DIR
from transformers import AutoTokenizer
def main():
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    demo_text = "Q: Who are you?\nA: I am a 1.58-bit LLM running on a ESP32 cluster."
    print("标准输入:", tokenizer(demo_text)["input_ids"])


if __name__ == "__main__":
    main()
