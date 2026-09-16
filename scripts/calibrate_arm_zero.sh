#!/bin/bash
# ===================================================================
# A7 / A7 Lite 独立零位标定入口
# 从 ../config/arm_config.yaml 读取 arm_type / left_arm / right_arm
# 直接调用 linkerbot-arm，不走 ROS2 节点。
# ===================================================================

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# 激活 data_collection 虚拟环境（与 scripts/start_arm.sh 一致）
VENV_PATH="$HOME/.venv/data_collection/bin/activate"
if [ ! -f "$VENV_PATH" ]; then
    echo "[ERROR] 虚拟环境不存在: $VENV_PATH" >&2
    echo "[ERROR] 请先创建: python3 -m venv ~/.venv/data_collection" >&2
    exit 1
fi
# shellcheck disable=SC1090
source "$VENV_PATH"

exec python3 "${SCRIPT_DIR}/calibrate_arm_zero.py" "$@"
