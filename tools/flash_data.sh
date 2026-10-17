#!/usr/bin/env bash
# macOS 版数据分区烧录脚本（替代仓库里的 flash_*.bat）
#
# 用法:
#   ./flash_data.sh master <port>                 # 烧 master 的 tokenizer + embed + final_norm
#   ./flash_data.sh node   <port> <layer_bin>     # 烧某个节点的层数据, 例如 layers_0_to_3.bin
#
# 端口示例: /dev/cu.usbmodemXXXX 或 /dev/cu.usbserial-XXXX (ls /dev/cu.* 查看)
#
# ⚠️ 烧录前: 断开该板 GPIO1 到别的板的 RST 连线（RST 必须浮空才能进下载模式）
# ⚠️ 节点板的物理链位必须与层文件匹配: Node1=0_to_3 ... Node6=20_to_23

set -euo pipefail

ROLE="${1:?用法: $0 master|node <port> [layer_bin]}"
PORT="${2:?请指定串口, 例如 /dev/cu.usbmodem101}"
BAUD=2000000
BIN_DIR="$(cd "$(dirname "$0")/.." && pwd)/cropped_Qwen"   # 数据 bin 所在目录

esptool_cmd() {
  uv run --project "$BIN_DIR/.." python -m esptool --chip esp32s3 --port "$PORT" --baud $BAUD write_flash "$@"
}

case "$ROLE" in
  master)
    echo ">> 烧录 tokenizer.bin   -> 0x90000"
    esptool_cmd 0x90000  "$BIN_DIR/tokenizer.bin"
    echo ">> 烧录 embed.bin       -> 0x150000"
    esptool_cmd 0x150000 "$BIN_DIR/bins/embed.bin"
    echo ">> 烧录 final_norm.bin  -> 0xFF0000"
    esptool_cmd 0xFF0000 "$BIN_DIR/bins/final_norm.bin"
    echo "✅ Master 数据分区烧录完成"
    ;;
  node)
    LAYER_BIN="${3:?node 模式需要指定层文件名, 例如 layers_0_to_3.bin}"
    FILE="$BIN_DIR/bins/$LAYER_BIN"
    if [[ ! -f "$FILE" ]]; then
      echo "❌ 找不到 $FILE"; ls "$BIN_DIR/bins/"; exit 1
    fi
    echo ">> 烧录 $LAYER_BIN -> 0x90000"
    esptool_cmd 0x90000 "$FILE"
    echo "✅ 节点数据分区烧录完成 ($LAYER_BIN)"
    ;;
  *)
    echo "❌ 未知角色: $ROLE (只能是 master 或 node)"; exit 1
    ;;
esac
