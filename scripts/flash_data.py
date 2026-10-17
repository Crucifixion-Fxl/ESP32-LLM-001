#!/usr/bin/env python3
"""Flash model data using an explicit board role and serial port; supports dry runs."""
import argparse
from pathlib import Path
import shlex
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]


def build_command(role, port, model_dir, layer_file=None, baud=2_000_000):
    if role == "master":
        segments = [("0x90000", model_dir / "tokenizer.bin"),
                    ("0x150000", model_dir / "bins/embed.bin"),
                    ("0xFF0000", model_dir / "bins/final_norm.bin")]
    elif role == "node":
        allowed = {f"layers_{i}_to_{i + 3}.bin" for i in range(0, 24, 4)}
        if layer_file not in allowed:
            raise ValueError("--layer must match the node position: " + ", ".join(sorted(allowed)))
        segments = [("0x90000", model_dir / "bins" / layer_file)]
    else:
        raise ValueError("role must be master or node")
    missing = [str(path) for _, path in segments if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing model files: " + ", ".join(missing))
    command = [sys.executable, "-m", "esptool", "--chip", "esp32s3", "--port", port,
               "--baud", str(baud), "write-flash"]
    for address, path in segments:
        command.extend([address, str(path)])
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=["master", "node"])
    parser.add_argument("--port", required=True, help="Serial device, e.g. /dev/cu.usbmodemXXXX or COM3")
    workspace = Path(os.environ.get("ESP32_LLM_WORKSPACE", str(ROOT))).expanduser()
    parser.add_argument("--model-dir", type=Path, default=workspace / "cropped_Qwen")
    parser.add_argument("--layer", help="Node layer filename, e.g. layers_0_to_3.bin")
    parser.add_argument("--baud", type=int, default=2_000_000)
    parser.add_argument("--dry-run", action="store_true", help="Validate files and print the command without touching hardware")
    args = parser.parse_args()
    if args.role == "master" and args.layer:
        parser.error("--layer is only used with node")
    try:
        command = build_command(args.role, args.port, args.model_dir.resolve(), args.layer, args.baud)
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))
    print(shlex.join(command), flush=True)
    if not args.dry_run:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
