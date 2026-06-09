#!/bin/bash
# Worldline Choice 启动脚本
# 默认启动新版 worldline_skill.py (v4.6.0 带 DC校准 + 收益系统 + 角色成长)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/worldline_skill.py" "$@"
