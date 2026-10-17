"""Download the base model and run both preparation stages (also usable outside Colab)."""
import urllib.request
from tools.paths import SOURCE_MODEL_DIR
from tools.prepare.crop_tokenizer import main as crop_tokenizer
from tools.prepare.crop_weights import main as crop_weights


def main():
    SOURCE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"):
        destination = SOURCE_MODEL_DIR / name
        if destination.exists():
            print(f"Using existing {destination}")
            continue
        temporary = destination.with_suffix(destination.suffix + ".part")
        print(f"Downloading {name}")
        urllib.request.urlretrieve(f"https://huggingface.co/Qwen/Qwen2-0.5B/resolve/main/{name}", temporary)
        temporary.replace(destination)
    crop_tokenizer()
    crop_weights()
    print("Ready: python -m tools.training.train_qat --steps 4000")


if __name__ == "__main__":
    main()
