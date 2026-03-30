#!/bin/bash
# Worldline Choice 启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/worldline_engine.py" "$@"
