@echo off
:: 設定編碼為 UTF-8，避免繁體中文顯示亂碼
chcp 65001 >nul

echo ========================================
echo          回報問題精靈 (Issue Reporter)    
echo ========================================

:ask_title
set "ISSUE_TITLE="
set /p "ISSUE_TITLE=1. 請輸入問題簡述/標題: "
if "%ISSUE_TITLE%"=="" (
    echo    [錯誤] 標題不能為空，請重新輸入！
    goto ask_title
)

:ask_desc
set "DESCRIPTION="
set /p "DESCRIPTION=2. 請輸入詳細描述 (可留空): "

echo ----------------------------------------
echo 確認您輸入的資訊：
echo   標題:     %ISSUE_TITLE%
echo   嚴重程度: %SEVERITY%
echo   描述:     %DESCRIPTION%
echo ----------------------------------------

:ask_confirm
set "CONFIRM="
set /p "CONFIRM=是否確認送出並執行回報？ [Y/n]: "
if /i "%CONFIRM%"=="n" (
    echo 已取消回報。
    goto end
)
if /i "%CONFIRM%"=="no" (
    echo 已取消回報。
    goto end
)

echo 正在啟動 report_issue.py...

:: 執行 Python 腳本並傳遞參數（帶引號避免空格被切斷）
.\venv\Scripts\python.exe report_issue.py --title "%ISSUE_TITLE%" --severity "%SEVERITY%" --description "%DESCRIPTION%"

echo.
echo 完成！

:end
pause
