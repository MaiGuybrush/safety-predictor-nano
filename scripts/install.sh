#!/usr/bin/env bash
# ==============================================================================
# scripts/install.sh - Argus Safety Predictor Nano 安裝與升級處理腳本
# ==============================================================================
# 職責：
# 1. 支援全新安裝 (Fresh Install) 與全量解壓升級 (Upgrade)。
# 2. 支援 Delta 增量補丁升級 (--delta <delta_tar_gz>)：
#    - 檢驗 manifest.json 與 package_type == "delta"。
#    - 局域原子置換：嚴格保留底層 _internal/ 中的所有重型動態函式庫 (PyTorch、OpenCV、NumPy 等)。
#    - 僅備份業務模組 argus.zip、Web 模板與手冊至 _internal/.patch_bak/。
#    - 原子替換新版 argus.zip 與前端靜態資源。
# 3. 升級時非破壞性零資料遺失：
#    - 嚴格保留使用者既有 config.yaml、models/ 與 logs/，永不覆蓋。
# 4. 支援快速雙模回滾 (--rollback)：
#    - 優先偵測 .patch_bak/ 執行秒級局部還原 (免搬移 1GB 全量目錄)。
#    - 若無 Delta 備份則回退至全量目錄還原 (argus_predictor_bak/)。
# 5. 自動設定所有二進位與 shell 腳本之 chmod +x 執行權限。
# ==============================================================================

set -euo pipefail

ORIGINAL_CWD="$(pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="${ARGUS_INSTALL_DIR:-$(dirname "$SCRIPT_DIR")}"
cd "$BASE_DIR"

NON_INTERACTIVE=false
DO_ROLLBACK=false
IS_DELTA=false
DELTA_PACKAGE=""

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
        --delta)
            IS_DELTA=true
            if [[ $# -gt 1 && "$2" != --* ]]; then
                DELTA_PACKAGE="$2"
                shift 2
            else
                shift 1
            fi
            ;;
        *)
            shift
            ;;
    esac
done

# 解析 DELTA_PACKAGE 的絕對路徑
if [[ -n "$DELTA_PACKAGE" ]]; then
    if [ -f "$ORIGINAL_CWD/$DELTA_PACKAGE" ]; then
        DELTA_PACKAGE="$ORIGINAL_CWD/$DELTA_PACKAGE"
    elif [ -d "$ORIGINAL_CWD/$DELTA_PACKAGE" ]; then
        DELTA_PACKAGE="$ORIGINAL_CWD/$DELTA_PACKAGE"
    elif [ -f "$BASE_DIR/$DELTA_PACKAGE" ]; then
        DELTA_PACKAGE="$BASE_DIR/$DELTA_PACKAGE"
    elif [ -d "$BASE_DIR/$DELTA_PACKAGE" ]; then
        DELTA_PACKAGE="$BASE_DIR/$DELTA_PACKAGE"
    fi
fi

# ------------------------------------------------------------------------------
# 1. 執行回滾程序 (--rollback)
# ------------------------------------------------------------------------------
if [ "$DO_ROLLBACK" = true ]; then
    echo "[install.sh] 執行自動回滾程序..."

    TARGET_DIR="argus_predictor"
    TARGET_INTERNAL=""
    if [ -d "$TARGET_DIR/_internal" ]; then
        TARGET_INTERNAL="$TARGET_DIR/_internal"
    elif [ -d "_internal" ]; then
        TARGET_DIR="."
        TARGET_INTERNAL="_internal"
    fi

    # 1.1 優先檢查是否存在 Delta 局部增量備份 (.patch_bak/)
    PATCH_BAK=""
    if [ -n "$TARGET_INTERNAL" ] && [ -d "$TARGET_INTERNAL/.patch_bak" ]; then
        PATCH_BAK="$TARGET_INTERNAL/.patch_bak"
    fi

    if [ -n "$PATCH_BAK" ]; then
        echo "[install.sh] 偵測到 Delta 增量備份 ($PATCH_BAK/)，執行局部秒級還原..."

        # 還原 argus.zip
        if [ -f "$PATCH_BAK/argus.zip" ]; then
            cp -f "$PATCH_BAK/argus.zip" "$TARGET_INTERNAL/argus.zip.tmp"
            mv -f "$TARGET_INTERNAL/argus.zip.tmp" "$TARGET_INTERNAL/argus.zip"
            echo "[install.sh] [✓] argus.zip 已原子還原至原版本"
        fi

        # 還原 Web 模板
        if [ -d "$PATCH_BAK/argus/web/templates" ]; then
            rm -rf "$TARGET_INTERNAL/argus/web/templates"
            mkdir -p "$TARGET_INTERNAL/argus/web"
            cp -a "$PATCH_BAK/argus/web/templates" "$TARGET_INTERNAL/argus/web/"
        fi
        if [ -d "$PATCH_BAK/templates" ]; then
            rm -rf "$TARGET_INTERNAL/templates"
            cp -a "$PATCH_BAK/templates" "$TARGET_INTERNAL/"
        fi

        # 還原使用者手冊
        if [ -d "$PATCH_BAK/docs" ]; then
            rm -rf "$TARGET_INTERNAL/docs"
            cp -a "$PATCH_BAK/docs" "$TARGET_INTERNAL/"
        fi

        # 還原 version.txt
        if [ -f "$PATCH_BAK/version.txt" ]; then
            cp -f "$PATCH_BAK/version.txt" "$TARGET_DIR/version.txt" 2>/dev/null || true
            if [ -f "version.txt" ]; then
                cp -f "$PATCH_BAK/version.txt" "version.txt" 2>/dev/null || true
            fi
            echo "[install.sh] [✓] 版本資訊已還原至: $(cat "$PATCH_BAK/version.txt" | tr -d '\r\n')"
        fi

        # 還原維運腳本
        if [ -d "$PATCH_BAK/scripts" ]; then
            DEST_SCRIPTS="$TARGET_DIR/scripts"
            [ -d "$DEST_SCRIPTS" ] || DEST_SCRIPTS="scripts"
            mkdir -p "$DEST_SCRIPTS"
            cp -a "$PATCH_BAK/scripts"/* "$DEST_SCRIPTS/" 2>/dev/null || true
            chmod +x "$DEST_SCRIPTS"/*.sh 2>/dev/null || true
            echo "[install.sh] [✓] 維運腳本 (scripts/) 已還原至原版本"
        fi

        # 清除備份目錄
        rm -rf "$PATCH_BAK"

        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        echo "系統未通過健康檢查，已於 ${TIMESTAMP} 自動安全回滾至原版本" > .rollback_alert
        echo "===================================================================="
        echo " [✓] Delta 局部回滾完成！已快速復原至穩定版本。"
        echo "===================================================================="
        exit 0
    fi

    # 1.2 若無 Delta 備份，則執行全量備份還原 (argus_predictor_bak/)
    if [ ! -d "argus_predictor_bak" ]; then
        echo "[install.sh] 錯誤: 找不到備份目錄 argus_predictor_bak/ 或 .patch_bak/，無法執行回滾。"
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
    echo "[install.sh] 全量回滾完成！"
    exit 0
fi

# ------------------------------------------------------------------------------
# 2. Delta 增量更新模式 (--delta)
# ------------------------------------------------------------------------------
if [ "$IS_DELTA" = true ]; then
    echo "===================================================================="
    echo " Argus Safety Predictor Nano Delta 增量更新程序"
    echo " 模式: [增量補丁 (Delta Patch)] 僅更新業務模組與前端靜態資源"
    echo "===================================================================="

    TARGET_DIR="argus_predictor"
    TARGET_INTERNAL=""
    if [ -d "$TARGET_DIR/_internal" ]; then
        TARGET_INTERNAL="$TARGET_DIR/_internal"
    elif [ -d "_internal" ]; then
        TARGET_DIR="."
        TARGET_INTERNAL="_internal"
    else
        echo "[install.sh] 錯誤: 找不到現有安裝環境 (argus_predictor/_internal 或 _internal/ 不存在)，無法執行 Delta 增量更新。請先執行完整安裝。"
        exit 1
    fi

    DELTA_ROOT=""
    DELTA_TEMP_DIR=""
    if [ -n "$DELTA_PACKAGE" ]; then
        if [ -f "$DELTA_PACKAGE" ]; then
            DELTA_TEMP_DIR="updates/staging"
            rm -rf "$DELTA_TEMP_DIR" 2>/dev/null || true
            mkdir -p "$DELTA_TEMP_DIR"
            echo "[install.sh] 正在解壓縮 Delta 增量包 $DELTA_PACKAGE 至 $DELTA_TEMP_DIR..."
            tar -xzf "$DELTA_PACKAGE" -C "$DELTA_TEMP_DIR"
            DELTA_ROOT="$DELTA_TEMP_DIR"
        elif [ -d "$DELTA_PACKAGE" ]; then
            DELTA_ROOT="$DELTA_PACKAGE"
        else
            echo "[install.sh] 錯誤: 指定之 Delta 增量包路徑不存在: $DELTA_PACKAGE"
            exit 1
        fi
    else
        if [ -f "updates/staging/manifest.json" ]; then
            DELTA_ROOT="updates/staging"
        elif [ -f "payload/../manifest.json" ] || [ -f "manifest.json" ]; then
            DELTA_ROOT="."
        else
            echo "[install.sh] 錯誤: 未指定 Delta 增量包且找不到暫存目錄 updates/staging/manifest.json"
            exit 1
        fi
    fi

    MANIFEST_FILE="$DELTA_ROOT/manifest.json"
    if [ ! -f "$MANIFEST_FILE" ]; then
        echo "[install.sh] 錯誤: 找不到 manifest.json，不是有效的 Delta 增量包。"
        exit 1
    fi

    # 驗證 package_type 為 delta
    if ! grep -q '"package_type"[[:space:]]*:[[:space:]]*"delta"' "$MANIFEST_FILE"; then
        echo "[install.sh] 錯誤: manifest.json 標記之 package_type 不是 delta。"
        exit 1
    fi

    DELTA_PAYLOAD="$DELTA_ROOT/payload"
    if [ ! -d "$DELTA_PAYLOAD" ]; then
        echo "[install.sh] 錯誤: Delta 增量包內找不到 payload/ 目錄。"
        exit 1
    fi

    # 建立 .patch_bak/ 局部備份
    PATCH_BAK="$TARGET_INTERNAL/.patch_bak"
    echo "[install.sh] 正在建立 Delta 備份至 $PATCH_BAK/..."
    rm -rf "$PATCH_BAK" 2>/dev/null || true
    mkdir -p "$PATCH_BAK"

    if [ -f "$TARGET_INTERNAL/argus.zip" ]; then
        cp -a "$TARGET_INTERNAL/argus.zip" "$PATCH_BAK/argus.zip"
    fi
    if [ -d "$TARGET_INTERNAL/argus/web/templates" ]; then
        mkdir -p "$PATCH_BAK/argus/web"
        cp -a "$TARGET_INTERNAL/argus/web/templates" "$PATCH_BAK/argus/web/"
    fi
    if [ -d "$TARGET_INTERNAL/templates" ]; then
        cp -a "$TARGET_INTERNAL/templates" "$PATCH_BAK/"
    fi
    if [ -d "$TARGET_INTERNAL/docs" ]; then
        cp -a "$TARGET_INTERNAL/docs" "$PATCH_BAK/"
    fi
    if [ -f "$TARGET_DIR/version.txt" ]; then
        cp -a "$TARGET_DIR/version.txt" "$PATCH_BAK/"
    elif [ -f "version.txt" ]; then
        cp -a "version.txt" "$PATCH_BAK/"
    fi

    # 備份維運腳本
    SRC_SCRIPTS="$TARGET_DIR/scripts"
    [ -d "$SRC_SCRIPTS" ] || SRC_SCRIPTS="scripts"
    if [ -d "$SRC_SCRIPTS" ]; then
        mkdir -p "$PATCH_BAK/scripts"
        cp -a "$SRC_SCRIPTS"/* "$PATCH_BAK/scripts/" 2>/dev/null || true
    fi

    # 執行局域原子替換
    echo "[install.sh] 正在套用 Delta 載荷至 $TARGET_DIR (底層重型動態函式庫嚴格保留)..."

    # 1. 原子替換 argus.zip
    if [ -f "$DELTA_PAYLOAD/_internal/argus.zip" ]; then
        cp -f "$DELTA_PAYLOAD/_internal/argus.zip" "$TARGET_INTERNAL/argus.zip.tmp"
        mv -f "$TARGET_INTERNAL/argus.zip.tmp" "$TARGET_INTERNAL/argus.zip"
        echo "[install.sh] [✓] argus.zip 已原子替換至新版本"
    fi

    # 2. 替換 Web 模板
    if [ -d "$DELTA_PAYLOAD/_internal/argus/web/templates" ]; then
        mkdir -p "$TARGET_INTERNAL/argus/web/templates"
        cp -a "$DELTA_PAYLOAD/_internal/argus/web/templates"/* "$TARGET_INTERNAL/argus/web/templates/" 2>/dev/null || true
    fi
    if [ -d "$DELTA_PAYLOAD/_internal/templates" ]; then
        mkdir -p "$TARGET_INTERNAL/templates"
        cp -a "$DELTA_PAYLOAD/_internal/templates"/* "$TARGET_INTERNAL/templates/" 2>/dev/null || true
    fi

    # 3. 替換手冊
    if [ -d "$DELTA_PAYLOAD/_internal/docs/user-manual/book" ]; then
        mkdir -p "$TARGET_INTERNAL/docs/user-manual/book"
        cp -a "$DELTA_PAYLOAD/_internal/docs/user-manual/book"/* "$TARGET_INTERNAL/docs/user-manual/book/" 2>/dev/null || true
    fi

    # 4. 替換版本資訊
    if [ -f "$DELTA_PAYLOAD/version.txt" ]; then
        cp -f "$DELTA_PAYLOAD/version.txt" "$TARGET_DIR/version.txt" 2>/dev/null || true
        if [ -f "version.txt" ]; then
            cp -f "$DELTA_PAYLOAD/version.txt" "version.txt" 2>/dev/null || true
        fi
        echo "[install.sh] [✓] 版本資訊已更新至: $(cat "$DELTA_PAYLOAD/version.txt" | tr -d '\r\n')"
    fi

    # 5. 替換維運腳本
    if [ -d "$DELTA_PAYLOAD/scripts" ]; then
        DEST_SCRIPTS="$TARGET_DIR/scripts"
        [ -d "$DEST_SCRIPTS" ] || DEST_SCRIPTS="scripts"
        mkdir -p "$DEST_SCRIPTS"
        cp -a "$DELTA_PAYLOAD/scripts"/* "$DEST_SCRIPTS/" 2>/dev/null || true
        chmod +x "$DEST_SCRIPTS"/*.sh 2>/dev/null || true
        echo "[install.sh] [✓] 維運腳本 (scripts/) 已更新至新版本"
    fi

    # 6. 清除暫存目錄
    if [ -n "$DELTA_TEMP_DIR" ] && [ -d "$DELTA_TEMP_DIR" ]; then
        rm -rf "$DELTA_TEMP_DIR" 2>/dev/null || true
    fi

    echo "===================================================================="
    echo " [✓] Delta 增量補丁套用完成！"
    echo " 既有重型動態函式庫、config.yaml、models/ 與 logs/ 皆完整保留未受更動。"
    echo " 備份已留存於 $PATCH_BAK/ (若需還原可執行 ./scripts/install.sh --rollback)"
    echo "===================================================================="
    exit 0
fi

# ------------------------------------------------------------------------------
# 3. 模式判定 (Fresh Install vs Upgrade - 全量模式)
# ------------------------------------------------------------------------------
IS_UPGRADE=false
if [ -d "argus_predictor" ] || [ -f "config.yaml" ]; then
    IS_UPGRADE=true
fi

echo "===================================================================="
echo " Argus Safety Predictor Nano 部署與安裝程序"
if [ "$IS_UPGRADE" = true ]; then
    echo " 模式: [全量升級模式 (Full Upgrade)] 零資料遺失防護已啟動"
else
    echo " 模式: [初次安裝 (Fresh Install)]"
fi
echo "===================================================================="

# ------------------------------------------------------------------------------
# 4. 全量升級模式：自動備份與防護
# ------------------------------------------------------------------------------
if [ "$IS_UPGRADE" = true ]; then
    echo "[install.sh] 正在備份目前運行環境至 argus_predictor_bak/..."
    rm -rf "argus_predictor_bak" 2>/dev/null || true
    mkdir -p "argus_predictor_bak"

    if [ -d "argus_predictor" ]; then
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
# 5. 解壓與載荷部署 (Payload Extraction)
# ------------------------------------------------------------------------------
PAYLOAD_DIR="./payload"
if [ ! -d "$PAYLOAD_DIR" ]; then
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
# 6. 配置檔與資料非破壞性處理 (Zero Data Loss)
# ------------------------------------------------------------------------------
if [ ! -f "config.yaml" ]; then
    if [ -f "argus_predictor/config.default.yaml" ]; then
        echo "[install.sh] 建立初始 config.yaml..."
        cp "argus_predictor/config.default.yaml" "config.yaml"
    fi
else
    echo "[install.sh] 保留既有使用者自訂 config.yaml，不予覆蓋。"
fi

mkdir -p "models" "logs" "updates/staging"

# ------------------------------------------------------------------------------
# 7. 權限設定 (chmod +x)
# ------------------------------------------------------------------------------
echo "[install.sh] 賦予可執行權限..."
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x argus_predictor/argus_predictor 2>/dev/null || true
chmod +x argus_predictor/*.sh 2>/dev/null || true

echo "===================================================================="
echo " [✓] 安裝/升級處理完成！"
echo " 可執行 ./scripts/run.sh 啟動服務。"
echo "===================================================================="
