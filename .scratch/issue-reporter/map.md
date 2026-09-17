# Effort: 診斷封包上傳與 Gitea Issue 自動回報 (Issue Reporter) (Gitea Epic: #59)

## Destination

產出完整的診斷資料打包、API Gateway 檔案服務上傳、以及 Gitea Issue 自動建立的技術架構與待實作 Tickets（包含 Web UI 與離線手動 CLI 工具），確認無待決策事項後進入實作。

## Notes

- **Domain**: Argus Safety Predictor Nano（邊緣端目標偵測、Flask Web UI、PyInstaller ARM64/x64 單一二進位執行檔）。
- **Issue Tracker**: 本專案遵循 `.scratch/issue-reporter/issues/` 之票券規範；Gitea 專案為 `guy.mai/safety-predictor-nano`，Epic Issue 為 [#59](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/59)。
- **認證與網路**: API Gateway 負責注入 Gitea Token，本機無須儲存金鑰；主機位址由 `ums-api-config.json` 解析；上傳端點為 `/FileServiceCore/File`。
- **安全規範**: 打包配置檔前必須遮蔽敏感金鑰（`ums_api_key`）及 RTSP 認證密碼。

## Decisions so far

- [#60 — 01 — 診斷封包收集器與敏感資料脫敏模組 (Diagnostic Bundle Collector)](issues/01-diagnostic-bundle-collector.md) — 實作 `diagnostic_collector.py`、脫敏遮蔽、全域 `sys.excepthook` 崩潰日誌與單檔 20MB 截斷保護打包為標準 ZIP 封包。
- [#61 — 02 — API Gateway 檔案上傳與 Gitea Issue 建立客戶端 (API Gateway Client)](issues/02-api-gateway-client.md) — 實作 `issue_service_client.py`，支援廠區動態主機解析、多 Gateway Failover 容錯切換、FileServiceCore 封包上傳及 Gitea Issue 自動建立。
- [#62 — 03 — 獨立離線手動回報 CLI 工具 (Offline CLI Reporter)](issues/03-offline-cli-reporter.md) — 實作 `report_issue.py`，支援互動提示與命令列參數，並在 `main.py` 整合 `--report-issue` 與 PyInstaller 打包支援，連線失敗時本機保留 `issue-bundles/` 封包指引。
- [#63 — 04 — Web UI 回報按鈕、Modal 與非同步回報 API (Web UI Report Issue Modal)](issues/04-web-ui-report-issue-modal.md) — 於導覽列提供 `[ 回報問題 REPORT ]` 按鈕與 Cyberpunk 風格彈出式 Modal，後端提供 `POST /api/issue/report` 非同步打包並發布至 Gitea。
- [#64 — 05 — 端到端整合測試與使用者操作手冊 (E2E Tests & User Manual)](issues/05-e2e-tests-and-user-manual.md) — 實作 30 項單元/整合與 E2E 測試驗證全流程與深度脫敏，並同步更新 mdBook 使用者操作手冊（第 2 章與第 6 章）。
- **檔案服務端點 (FileServiceCore)**: 使用 API Gateway 提供的 `/FileServiceCore/File` 進行 Multipart/form-data 上傳，並組裝直接下載連結。
- **Gitea Issue 建立通道**: 呼叫 Gateway 的 `/ApiGateway/git-server/api/v1/repos/guy.mai/safety-predictor-nano/issues`，Token 由 Gateway 自動代入。
- **雙入口支援**: 支援在線 Web UI 導覽列按鈕彈出 Modal，以及離線獨立工具 `report_issue.py` / `argus_predictor --report-issue`。
- **Crash 日誌收集**: 於系統進入點註冊 `sys.excepthook`，未捕捉例外自動落地至 `logs/crash.log` 納入封包。

## Not yet specified

<!-- 當前所有規劃之核心架構與例外處理已具體轉化為票券，無殘留模糊需求 -->

## Out of scope

- 即時高畫質視訊錄影檔案打包（因容量過大且影響 CPU 負載，排除於診斷封包外）。
- 於 Web UI 內實作完整的 Gitea Issue 瀏覽、留言或狀態管理（直接提供外部 Gitea Issue 連結）。
