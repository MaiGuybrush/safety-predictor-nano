#!/bin/sh
# 嚴格模式：遇錯即停
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

${SCRIPT_DIR}/argus_predictor --report-issue