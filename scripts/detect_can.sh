#!/bin/bash
# ===================================================================
# CAN 设备自动检测脚本
# 自动输入密码执行 detect_can 程序
# 用法: bash scripts/detect_can.sh
# ===================================================================

# 密码配置（如需修改请在此处更改，或通过环境变量 PASSWORD 传入）
PASSWORD="${PASSWORD:-linkerhand}"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[→]${NC} $1"; }

# 获取脚本目录
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
DETECT_CAN="${SCRIPT_DIR}/detect_can"

# 检查 detect_can 是否存在
if [ ! -f "$DETECT_CAN" ]; then
    log_error "找不到 detect_can 程序: $DETECT_CAN"
    log_step "请先编译: g++ scripts/detect_can.cpp -std=c++17 -o scripts/detect_can"
    exit 1
fi

# 检查是否有执行权限
if [ ! -x "$DETECT_CAN" ]; then
    log_step "添加执行权限..."
    chmod +x "$DETECT_CAN"
fi

log_info "开始检测 CAN 设备..."
log_step "使用 sudo 执行 detect_can..."

# 使用 -S 选项让 sudo 从 stdin 读取密码
echo "$PASSWORD" | sudo -S "$DETECT_CAN"

