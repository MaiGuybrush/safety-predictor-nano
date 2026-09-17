#!/bin/sh
# 嚴格模式：遇錯即停
set -e

echo "========================================"
echo "         回報問題精靈 (Issue Reporter)    "
echo "========================================"

# 問題 1：問題標題 (必填檢查)
while [ -z "$ISSUE_TITLE" ]; do
    printf "1. 請輸入問題簡述/標題: "
    read -r ISSUE_TITLE
    if [ -z "$ISSUE_TITLE" ]; then
        echo "   [錯誤] 標題不能為空，請重新輸入！"
    fi
done

# 問題 2：詳細描述 (選填)
printf "3. 請輸入詳細描述 (可留空): "
read -r DESCRIPTION

echo "----------------------------------------"
echo "確認您輸入的資訊："
echo "  標題:     $ISSUE_TITLE"
echo "  嚴重程度: $SEVERITY"
echo "  描述:     $DESCRIPTION"
echo "----------------------------------------"

# 確認是否送出
printf "是否確認送出並執行回報？ [Y/n]: "
read -r CONFIRM
case "$CONFIRM" in
    [nN][oO]|[nN])
        echo "已取消回報。"
        exit 0
        ;;
    *)
        echo "正在啟動 report_issue.py..."
        ;;
esac

# 觸發 Python 腳本並傳入參數
./venv/Scripts/python report_issue.py \
    --title "$ISSUE_TITLE" \
    --severity "$SEVERITY" \
    --description "$DESCRIPTION"

echo "完成！"
