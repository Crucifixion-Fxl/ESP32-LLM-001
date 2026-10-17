#!/usr/bin/env bash
# Use an existing CUDA image with the repository's Python dependencies installed.
set -euo pipefail
if [[ ${1:-} == --help || $# == 0 ]]; then
  echo "Usage: $0 IMAGE [train_qat arguments...]"
  echo 'Set GPUS to a Docker GPU selector (default: all). No existing container is removed.'
  exit 0
fi
image="$1"
shift
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker run --rm --gpus "${GPUS:-all}" --shm-size=8g \
  -v "$repo_root:/workspace" -w /workspace "$image" \
  python -m tools.training.train_qat "$@"
