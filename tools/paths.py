"""Shared artifact paths; independent of a tool's directory or working directory."""
import os
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(os.environ.get("ESP32_LLM_WORKSPACE", str(REPOSITORY_ROOT))).expanduser().resolve()
SOURCE_MODEL_DIR = WORKSPACE / "Qwen2-0.5B"
MODEL_DIR = WORKSPACE / "cropped_Qwen"
