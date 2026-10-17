#!/usr/bin/env bash
# dev-4090 上的部署脚本：重建容器 + 准备脚本 + 启动训练
set -e

# 1. 重建容器（挂正确的家目录）
docker rm -f DEV_KINEAI_FXL > /dev/null 2>&1 || true
docker run -d --name DEV_KINEAI_FXL \
  --gpus '"device=2"' --shm-size=8g --restart=unless-stopped \
  -v $HOME:/ws \
  caoxh_torch:latest sleep infinity > /dev/null

# 2. 修补路径（Colab 的 /content 前缀 -> 容器内 /ws/esp32-llm）
docker exec DEV_KINEAI_FXL sed -i 's|/content/|/ws/esp32-llm/|g' /ws/esp32-llm/colab_prepare.py

# 3. 依赖（torch 已内置，补 transformers/datasets/safetensors）
docker exec DEV_KINEAI_FXL pip install -q transformers datasets safetensors 2>&1 | grep -v notice || true

# 4. 验证环境
docker exec DEV_KINEAI_FXL python3 - <<'EOF'
import torch, transformers, datasets, safetensors
print("deps OK | torch", torch.__version__, "| gpu:", torch.cuda.get_device_name(0), "| bf16:", torch.cuda.is_bf16_supported())
EOF

# 5. 模型准备（下载 Qwen2-0.5B + 32K 裁剪，约 3-5 分钟）
docker exec -w /ws/esp32-llm DEV_KINEAI_FXL python3 colab_prepare.py 2>&1 | tail -5

# 6. tmux 里启动训练（断线不挂）
docker exec DEV_KINEAI_FXL bash -c 'tmux new-session -d -s train "cd /ws/esp32-llm && python3 qat_speak.py --steps 1600 2>&1 | tee train.log" || (apt-get install -y -q tmux > /dev/null 2>&1 && tmux new-session -d -s train "cd /ws/esp32-llm && python3 qat_speak.py --steps 1600 2>&1 | tee train.log")'

echo "=== 部署完成，10 秒后训练日志开头 ==="
sleep 10
docker exec DEV_KINEAI_FXL bash -c 'tail -5 /ws/esp32-llm/train.log 2>/dev/null || tmux capture-pane -t train -p | tail -5'
