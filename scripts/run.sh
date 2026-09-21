#!/usr/bin/env bash
# ==============================================================================
# scripts/run.sh - Argus Safety Predictor Nano 守護啟動腳本
# ==============================================================================
# 職責：
# 1. 強制鎖定 CWD 工作目錄為程式所在根目錄，遵循 ADR-005。
# 2. 設定樹莓派 5 (ARM64) 最佳化環境變數 (執行緒數、記憶體配置、OpenCV RTSP TCP 傳輸)。
# 3. 提供外層監聽守護迴圈：
#    - 當主二進位程序返回 Exit Code 42 (RESTART_FOR_UPDATE) 時，自動重新載入新版程式。
#    - 當返回 Exit Code 0 時，正常退出。
#    - 當遭遇異常崩潰 (非 0 且非 42) 時，若檢測到正在升級中 (.update_in_progress)，觸發自動回滾。
# ==============================================================================

set -euo pipefail

# 1. 強制工作目錄鎖定 (ADR-005)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

echo "[run.sh] 工作目錄鎖定至: $(pwd)"

# 2. RPi 5 最佳化環境變數注入
export PYTHONUNBUFFERED=1
export OPENCV_LOG_LEVEL=ERROR
export OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"
export OMP_NUM_THREADS=4
export MALLOC_ARENA_MAX=2

# 若有 _internal/ 則優先載入動態庫
if [ -d "./argus_predictor/_internal" ]; then
    export LD_LIBRARY_PATH="./argus_predictor/_internal:${LD_LIBRARY_PATH:-}"
elif [ -d "./_internal" ]; then
    export LD_LIBRARY_PATH="./_internal:${LD_LIBRARY_PATH:-}"
fi

# 決定執行檔路徑
BINARY_PATH="./argus_predictor/argus_predictor"
if [ ! -f "$BINARY_PATH" ]; then
    if [ -f "./argus_predictor" ]; then
        BINARY_PATH="./argus_predictor"
    elif [ -f "./main.py" ]; then
        BINARY_PATH="python3 main.py"
    else
        echo "[run.sh] 錯誤: 找不到可執行之 argus_predictor 二進位檔或 main.py"
        exit 1
    fi
fi

# 3. 守護重啟迴圈 (Exit Code 42 監聽)
while true; do
    echo "[run.sh] 正在啟動 Argus Safety Predictor Nano: $BINARY_PATH $@"
    
    # 執行主程式並捕捉 Exit Code
    set +e
    $BINARY_PATH "$@"
    EXIT_CODE=$?
    set -e

    echo "[run.sh] 行程結束，Exit Code: $EXIT_CODE"

    if [ "$EXIT_CODE" -eq 42 ]; then
        echo "[run.sh] 收到重啟代碼 42 (RESTART_FOR_UPDATE)，準備載入新版本..."
        sleep 1
        continue
    elif [ "$EXIT_CODE" -eq 0 ]; then
        echo "[run.sh] 程式正常結束 (Exit 0)，退出守護迴圈。"
        break
    else
        # 異常退出檢查是否處於更新窗口
        if [ -f ".update_in_progress" ]; then
            echo "[run.sh] 警告: 更新期間發生異常崩潰 (Exit Code: $EXIT_CODE)，啟動自動回滾程序..."
            if [ -f "./scripts/install.sh" ]; then
                ./scripts/install.sh --rollback || true
            elif [ -d "argus_predictor_bak" ]; then
                rm -rf "argus_predictor_failed_$(date +%s)" 2>/dev/null || true
                mv argus_predictor "argus_predictor_failed_$(date +%s)" 2>/dev/null || true
                mv argus_predictor_bak argus_predictor
                echo "升級異常崩潰 (Code: $EXIT_CODE)，已自動回滾至上一版本" > .rollback_alert
            fi
            rm -f ".update_in_progress"
            echo "[run.sh] 回滾完成，重新喚醒舊版本..."
            sleep 2
            continue
        fi
        echo "[run.sh] 程式異常終止 (Code: $EXIT_CODE)，退出。"
        exit "$EXIT_CODE"
    fi
done
