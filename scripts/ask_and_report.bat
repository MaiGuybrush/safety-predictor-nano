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

echo 正在啟動問題回報工具 (main.py --report-issue)...

:: 切換至專案根目錄（此腳本位於 scripts/ 目錄下）
pushd "%~dp0\.."

:: 優先支援二進位發布環境，若無則回退至 Python 腳本
if exist ".\argus_predictor.exe" (
    .\argus_predictor.exe --report-issue --title "%ISSUE_TITLE%" --severity "%SEVERITY%" --description "%DESCRIPTION%"
) else if exist ".\venv\Scripts\python.exe" (
    .\venv\Scripts\python.exe main.py --report-issue --title "%ISSUE_TITLE%" --severity "%SEVERITY%" --description "%DESCRIPTION%"
) else (
    python main.py --report-issue --title "%ISSUE_TITLE%" --severity "%SEVERITY%" --description "%DESCRIPTION%"
)
popd

echo.
echo 完成！

:end
pause
