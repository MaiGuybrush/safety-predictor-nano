# 05 — 端到端整合測試與使用者操作手冊 (E2E Tests & User Manual)

Gitea Issue: #64
Type: task
Status: resolved
Blocked by: 03, 04

## Question
如何驗證整體診斷回報流程（包含脫敏正確性、Web UI 操作、CLI 指令、Gateway 模擬回應），並更新操作手冊指導現場維運與使用者？

## Tasks
- [x] 整合測試編寫：
  - [x] 撰寫 `test_diagnostic_collector.py` 驗證檔案收集與 config 脫敏過濾。
  - [x] 撰寫 `test_issue_service_client.py` 搭配 Mock HTTP Server 驗證上傳與 Issue 建立流程。
  - [x] 撰寫 `test_offline_cli.py` 驗證 CLI 指令解析與回報觸發。
  - [x] 撰寫 `test_web_ui_report_issue.py` 驗證 Web UI 元素與後端 API 整合。
  - [x] 撰寫 `test_e2e_issue_reporting.py` 涵蓋全流程整合驗證（真實檔案生成、深度脫敏、ZIP 內容校驗與離線回退）。
- [x] 操作手冊更新：
  - [x] 於 `docs/user-manual/src/06-system-settings.md` 新增「6. 問題診斷與異常回報 (Issue Reporter)」專節。
  - [x] 於 `docs/user-manual/src/02-ui-overview.md` 更新頂部狀態列 `[ 回報問題 REPORT ]` 按鈕說明。
  - [x] 記錄 Web UI 回報問題的使用步驟與畫面指引。
  - [x] 記錄當系統無法啟動時，如何使用命令列指令（`python report_issue.py` 或 `./argus_predictor --report-issue`）手動打包發送。
  - [x] 記錄無網路斷線環境之本機 `issue-bundles/` 封包留存機制與全域崩潰日誌攔截。
  - [x] 執行 `mdbook build docs/user-manual` 確保手冊編譯通過。

## Answer
1. **測試套件覆蓋與 E2E 整合驗證**：
   - 完成單元與整合測試套件：[test_diagnostic_collector.py](file:///D:/Projects/argus/safty-predictor-nano/test_diagnostic_collector.py)、[test_issue_service_client.py](file:///D:/Projects/argus/safty-predictor-nano/test_issue_service_client.py)、[test_offline_cli.py](file:///D:/Projects/argus/safty-predictor-nano/test_offline_cli.py)、[test_web_ui_report_issue.py](file:///D:/Projects/argus/safty-predictor-nano/test_web_ui_report_issue.py)。
   - 建立全流程 E2E 整合測試 [test_e2e_issue_reporting.py](file:///D:/Projects/argus/safty-predictor-nano/test_e2e_issue_reporting.py)，驗證真實日誌與配置脫敏、ZIP 內容嚴格檢查（驗證 `ums_api_key` 與 RTSP/URL 密碼不洩漏）、Web UI API 整合與斷網時本地 `issue-bundles/` 留存退出碼機制。
   - 強化 [diagnostic_collector.py](file:///D:/Projects/argus/safty-predictor-nano/diagnostic_collector.py) 之深度遞迴脫敏演算法 `_mask_obj_recursively`，全數 30 項測試皆通過。
2. **使用者操作手冊同步更新**：
   - 於 [02-ui-overview.md](file:///D:/Projects/argus/safty-predictor-nano/docs/user-manual/src/02-ui-overview.md) 更新頂部狀態列按鈕說明與導覽。
   - 於 [06-system-settings.md](file:///D:/Projects/argus/safty-predictor-nano/docs/user-manual/src/06-system-settings.md) 撰寫完整的「第 6 節：問題診斷與異常回報 (Issue Reporter)」，包含 Web UI 操作步驟、欄位說明、離線 CLI（原始碼模式與 PyInstaller 獨立執行檔）手動指令範例、斷網本機封包留存與全域崩潰日誌攔截說明。
   - 執行 `mdbook build docs/user-manual` 編譯通過，產出完整 HTML 手冊。
