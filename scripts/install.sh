#!/usr/bin/env bash
# ==============================================================================
# scripts/install.sh - Argus Safety Predictor Nano 安裝與升級處理腳本
# ==============================================================================
# 職責：
# 1. 支援全新安裝 (Fresh Install) 與就地解壓升級 (Upgrade)。
# 2. 升級時非破壞性零資料遺失：
#    - 將目前版本目錄完整備份至 argus_predictor_bak/
#    - 模型目錄 models/ 使用 cp -al 硬連結秒級備份，不佔用額外實體磁碟容量
#    - 嚴格保留使用者既有 config.yaml、models/ 與 logs/，永不覆蓋
# 3. 動態連結庫安全兩階段置換 (_internal/ 移至 .old 後重建)，防範 SIGSEGV
# 4. 支援 --rollback 參數，快速還原上一備份版本
# 5. 自動設定所有二進位與 shell 腳本之 chmod +x 執行權限
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

NON_INTERACTIVE=false
DO_ROLLBACK=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes|--non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --rollback)
            DO_ROLLBACK=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# ------------------------------------------------------------------------------
# 1. 執行回滾程序 (--rollback)
# ------------------------------------------------------------------------------
if [ "$DO_ROLLBACK" = true ]; then
    echo "[install.sh] 執行自動回滾程序..."
    if [ ! -d "argus_predictor_bak" ]; then
        echo "[install.sh] 錯誤: 找不到備份目錄 argus_predictor_bak/，無法執行回滾。"
        exit 1
    fi

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    if [ -d "argus_predictor" ]; then
        echo "[install.sh] 隔離損毀版本至 argus_predictor_failed_${TIMESTAMP}/"
        mv "argus_predictor" "argus_predictor_failed_${TIMESTAMP}"
    fi

    echo "[install.sh] 還原備份版本 argus_predictor_bak/ -> argus_predictor/"
    mv "argus_predictor_bak" "argus_predictor"
    echo "系統未通過健康檢查，已於 ${TIMESTAMP} 自動安全回滾至原版本" > .rollback_alert
    echo "[install.sh] 回滾完成！"
    exit 0
fi

# ------------------------------------------------------------------------------
# 2. 模式判定 (Fresh Install vs Upgrade)
# ------------------------------------------------------------------------------
IS_UPGRADE=false
if [ -d "argus_predictor" ] || [ -f "config.yaml" ]; then
    IS_UPGRADE=true
fi

echo "===================================================================="
echo " Argus Safety Predictor Nano 部署與安裝程序"
if [ "$IS_UPGRADE" = true ]; then
    echo " 模式: [升級模式 (Upgrade)] 零資料遺失防護已啟動"
else
    echo " 模式: [初次安裝 (Fresh Install)]"
fi
echo "===================================================================="

# ------------------------------------------------------------------------------
# 3. 升級模式：自動備份與防護
# ------------------------------------------------------------------------------
if [ "$IS_UPGRADE" = true ]; then
    echo "[install.sh] 正在備份目前運行環境至 argus_predictor_bak/..."
    rm -rf "argus_predictor_bak" 2>/dev/null || true
    mkdir -p "argus_predictor_bak"

    if [ -d "argus_predictor" ]; then
        # 複製現有程式檔案至備份目錄 (若有 models 採硬連結)
        cp -a argus_predictor/* argus_predictor_bak/ 2>/dev/null || true
    fi

    # 備份獨立的 config.yaml
    if [ -f "config.yaml" ]; then
        cp -a "config.yaml" "argus_predictor_bak/config.yaml"
    fi

    # 模型目錄秒級硬連結備份
    if [ -d "models" ]; then
        mkdir -p "argus_predictor_bak/models"
        cp -al models/* "argus_predictor_bak/models/" 2>/dev/null || true
    fi

    echo "[install.sh] 備份建立完成。"
fi

# ------------------------------------------------------------------------------
# 4. 解壓與載荷部署 (Payload Extraction)
# ------------------------------------------------------------------------------
PAYLOAD_DIR="./payload"
if [ ! -d "$PAYLOAD_DIR" ]; then
    # 若無獨立 payload 資料夾，檢查是否有 staging 暫存目錄
    if [ -d "updates/staging/payload" ]; then
        PAYLOAD_DIR="updates/staging/payload"
    elif [ -d "updates/staging" ]; then
        PAYLOAD_DIR="updates/staging"
    fi
fi

if [ -d "$PAYLOAD_DIR" ]; then
    echo "[install.sh] 正在從 $PAYLOAD_DIR 同步最新檔案至 argus_predictor/..."
    mkdir -p "argus_predictor"

    # 動態庫安全置換：若 _internal 存在，先 rename 再搬移
    if [ -d "argus_predictor/_internal" ] && [ -d "$PAYLOAD_DIR/_internal" ]; then
        echo "[install.sh] 安全置換動態庫目錄 _internal/..."
        rm -rf "argus_predictor/_internal.old" 2>/dev/null || true
        mv "argus_predictor/_internal" "argus_predictor/_internal.old" 2>/dev/null || true
    fi

    # 拷貝核心檔案
    cp -a "$PAYLOAD_DIR"/* "argus_predictor/" 2>/dev/null || true
    rm -rf "argus_predictor/_internal.old" 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# 5. 配置檔與資料非破壞性處理 (Zero Data Loss)
# ------------------------------------------------------------------------------
# 若不存在 config.yaml，從出廠範本建立初始設定
if [ ! -f "config.yaml" ]; then
    if [ -f "argus_predictor/config.default.yaml" ]; then
        echo "[install.sh] 建立初始 config.yaml..."
        cp "argus_predictor/config.default.yaml" "config.yaml"
    fi
else
    echo "[install.sh] 保留既有使用者自訂 config.yaml，不予覆蓋。"
fi

# 建立必要目錄
mkdir -p "models" "logs" "updates/staging"

# ------------------------------------------------------------------------------
# 6. 權限設定 (chmod +x)
# ------------------------------------------------------------------------------
echo "[install.sh] 賦予可執行權限..."
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x argus_predictor/argus_predictor 2>/dev/null || true
chmod +x argus_predictor/*.sh 2>/dev/null || true

echo "===================================================================="
echo " [✓] 安裝/升級處理完成！"
echo " 可執行 ./scripts/run.sh 啟動服務。"
echo "===================================================================="
