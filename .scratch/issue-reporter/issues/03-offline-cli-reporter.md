# 03 — 獨立離線手動回報 CLI 工具 (Offline CLI Reporter)

Gitea Issue: #62
Type: task
Status: resolved
Blocked by: 01, 02

## Question
當 `main.py` 遭遇環境錯誤、配置損毀或相依性異常而無法正常啟動 Web UI 時，如何讓維運人員能夠透過獨立指令或 CLI 參數，手動觸發封包收集、上傳與 Gitea Issue 建立？

## Tasks
- [x] 實作獨立指令碼 `report_issue.py`：
  - [x] 支援互動式 CLI 提示（Prompt 使用者輸入問題標題、詳細狀況）。
  - [x] 支援命令列參數（如 `--title`, `--desc`, `--non-interactive`）。
  - [x] 串接 `diagnostic_collector` 進行本機打包。
  - [x] 串接 `issue_service_client` 上傳封包至 `FileServiceCore` 並建立 Gitea Issue。
  - [x] 於終端輸出詳細進度與建立成功的 Gitea Issue URL。
- [x] 於 `main.py` 增加 CLI 參數解析 `--report-issue`，委派執行回報邏輯。
- [x] 更新 PyInstaller 打包清單與 entry point 確保打包為單一執行檔時可直接執行 `argus_predictor --report-issue`。

## Answer
實作完成 [report_issue.py](file:///D:/Projects/argus/safty-predictor-nano/report_issue.py) 與整合入口：
1. **獨立 CLI 指令碼 ([report_issue.py](file:///D:/Projects/argus/safty-predictor-nano/report_issue.py))**：
   - 支援互動式問答提示（當未帶參數且處於 TTY 終端時引導使用者輸入標題與描述）與非互動參數模式（`--title`, `--desc`, `--non-interactive`）。
   - 串接 `diagnostic_collector` 執行系統日誌、脫敏配置與系統環境打包至 `issue-bundles/`。
   - 串接 `issue_service_client` 透過 API Gateway 上傳至 `FileServiceCore` 並自動於 Gitea 建立 Issue。
   - 完整的失敗容錯提示：當網路中斷或上傳失敗時，明確指引本機封包留存路徑供手動排查。
2. **系統進入點整合 ([main.py](file:///D:/Projects/argus/safty-predictor-nano/main.py))**：
   - 於進入點支援 `--report-issue` / `-r` 參數，自動委派執行 `report_issue.run_cli()`，無須啟動 Web UI 或影像擷取管線。
3. **單一二進位執行檔打包設定 ([argus_predictor.spec](file:///D:/Projects/argus/safty-predictor-nano/argus_predictor.spec))**：
   - 更新 PyInstaller 配置之 `datas` 與 `hiddenimports`（包含 `report_issue`, `diagnostic_collector`, `issue_service_client`），支援編譯後直接執行 `./argus_predictor --report-issue`。
4. **單元測試驗證 ([test_offline_cli.py](file:///D:/Projects/argus/safty-predictor-nano/test_offline_cli.py))**：
   - 涵蓋參數解析、打包失敗、上傳失敗容錯、建立 Issue 失敗以及 `main.py` 委派調用等 6 項測試，全數測試通過。

