# Effort: 自動更新機制與安全升級藍圖 (Auto-Update Mechanism)

## Destination

制定並交付《Argus Safety Predictor Nano 自動更新機制架構規格 (ADR) 與邊緣端安全升級決策藍圖》，完整定義串接 App Management API (`/App/{appId}/Version`, `/File/{appId}/DownloadInfo`, `/File/{appId}`) 進行版本檢查與下載、打包規格包含 `install.sh` 與啟動腳本、手動執行情境下的原子替換與狀態機、自動重啟/通知模式，以及 30 秒健康檢查自動回滾策略。

## Notes

- **Domain**: Argus Safety Predictor Nano（邊緣端 Raspberry Pi 5 目標偵測、Flask Web UI、PyInstaller `--onedir` 手動執行部署模式）。
- **Issue Tracker**: 本地票券路徑 `.scratch/auto-update-mechanism/issues/`；Gitea 專案為 `guy.mai/safety-predictor-nano`，Epic Issue 為 [#75](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/75)。
- **App Management API 規範**:
  - API Gateway 端點：`http://tncimweb.cminl.oa/appmanagementapi`
  - 版本查詢：`GET /App/{appId}/Version`（篩選 `released == true` 且 `autoUpdate == true`）
  - 下載資訊：`GET /File/{appId}/DownloadInfo?version={version}`
  - 封包下載：`GET /File/{appId}?owner={owner}&version={version}&filePath={filePath}`
- **執行與部署情境**:
  - 依循 `README.md` 方案 C（`--onedir` 產出之 `argus_predictor/` 資料夾）打包為壓縮檔（如 `.tar.gz`）。
  - 壓縮包內需提供 `install.sh` 處理安裝/更新程序，並提供便利的 Shell 啟動腳本。
  - 升級程序必須非破壞性地保留使用者既有的 `config.yaml`、模型目錄 `models/` 與日誌 `logs/`。
- **更新模式**:
  - 模式 1：無人值守自動替換並重啟。
  - 模式 2：Web UI 提示有新版本，由使用者確認或點擊重啟生效（預設模式）。
  - 兩者可透過 `config.yaml` 設定調整，預設為模式 2。
- **健康檢查與回滾**:
  - 新版本啟動後執行 30 秒健康狀態監控（Web UI 正常回應、推論引擎正常加載）。
  - 若逾時未就緒或崩潰，自動回滾至前一版本目錄備份（`argus_predictor_bak/`）並恢復啟動。
- **相關規範與 ADR**:
  - ADR-005：ARM64 建置與工作目錄約束（二進位檔必須與 `config.yaml` 同目錄）。
  - ADR-013：UMS 模型同步架構。

## Decisions so far

<!-- the index — one line per closed ticket: enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [01 — App Management API 客戶端與設定檔 Schema 設計](issues/01-app-management-api-client-and-config-schema.md) — 整合 App Management API (v9.2.0)，設計具備 Failover 容錯、1MB 串流下載與節流進度回呼的 AppUpdateClient，並定義 config.yaml 之 auto_update 設定結構與 SemVer 2.0 過濾規則。([Gitea #76](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/76))
- [02 — --onedir 封裝結構、安裝更新腳本 (install.sh) 與啟動腳本設計](issues/02-onedir-packaging-install-and-runner-scripts.md) — 制定包含 install.sh 與 run.sh 之 .tar.gz 發布包規範，實作自動備份至 argus_predictor_bak/、零資料遺失（嚴格保留 config.yaml/models/logs）、動態庫兩階段安全替換與 CWD 工作目錄鎖定。([Gitea #77](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/77))
- [03 — 原子目錄替換與行程自我重啟生命週期](issues/03-atomic-self-update-and-restart-lifecycle.md) — 定義 Staging 暫存驗證、雙重自我重啟機制（run.sh 守護迴圈 Exit 42 + Detached updater_helper.sh）、雙模式（無人值守 vs 提示確認）狀態機與前端 30 秒倒數輪詢重載體驗。([Gitea #78](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/78))
- [04 — 30 秒健康狀態判定與自動回滾容錯策略](issues/04-30s-healthcheck-and-auto-rollback-strategy.md) — 制定三階段健康檢查指標（進程存活、/api/health 探針、首幀推論完成），建立 30 秒評估窗口與 Commit 機制，並設計隔離現場、原子還原 argus_predictor_bak/、Web UI 告警橫幅與死迴圈防護之五步驟回滾程序。([Gitea #79](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/79))
- [05 — Web UI 更新狀態展示、通知與 SSE 下載進度條原型](issues/05-web-ui-update-interaction-and-sse-status.md) — 實作包含 Cyberpunk 導覽列版本標籤、呼吸發光更新徽章、四格指標彈窗、SSE 實時下載進度條與 30 秒全螢幕重啟探針輪詢重連之活原型，並交付獨立預覽展示頁與全套自動化端點測試。([Gitea #80](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/80))
- [06 — 產出正式架構決策記錄 (ADR-019) 與實作計畫規範](issues/06-auto-update-architecture-decision-record-adr.md) — 正式確立 ADR-019 架構決策記錄，整合 App Management API、--onedir Staging 目錄原子替換、Exit 42/Detached Helper 雙重自我重啟、30 秒健康評估與五步驟自動回滾管線，並在 spec.md 交付完整實作計畫與測試驗證清單。([Gitea #81](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/81))

## Not yet specified

<!-- see "Fog of war": in-scope fog you can't ticket yet; graduates as the frontier advances -->

- 離線 USB 隨身碟更新機制：針對隔離廠區或無任何內部網路連線之邊緣裝置，支援插拔隨身碟自動驗證簽章並執行升級。
- 遠端批次觸發與集中式監控：透過中央服務（如 UMS / Central Console）向多台邊緣樹莓派廣播更新指令與收集回報版本狀態。

## Out of scope

<!-- see "Out of scope": work ruled beyond the destination; closed, never graduates -->

- 部署程式包體積縮小（套件瘦身）：使用者明確指示非本次必要條件，本次專注於自動更新架構與安全機制，體積優化獨立於後續評估。
- 跨架構編譯（Cross-compilation）：依據 ADR-005 決策，打包建置依舊在 ARM64 環境產出。

## Issues

- [x] [01 — App Management API 客戶端與設定檔 Schema 設計](issues/01-app-management-api-client-and-config-schema.md) (Gitea [#76](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/76))
- [x] [02 — --onedir 封裝結構、安裝更新腳本 (install.sh) 與啟動腳本設計](issues/02-onedir-packaging-install-and-runner-scripts.md) (Gitea [#77](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/77))
- [x] [03 — 原子目錄替換與行程自我重啟生命週期 (Atomic Replacement & Restart Lifecycle)](issues/03-atomic-self-update-and-restart-lifecycle.md) (Gitea [#78](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/78))
- [x] [04 — 30 秒健康狀態判定與自動回滾容錯策略 (Healthcheck & Auto-Rollback Strategy)](issues/04-30s-healthcheck-and-auto-rollback-strategy.md) (Gitea [#79](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/79))
- [x] [05 — Web UI 更新狀態展示、通知與 SSE 下載進度條原型 (Web UI Update UX & SSE Status)](issues/05-web-ui-update-interaction-and-sse-status.md) (Gitea [#80](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/80))
- [x] [06 — 產出正式架構決策記錄 (ADR-019) 與實作計畫規範](issues/06-auto-update-architecture-decision-record-adr.md) (Gitea [#81](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/81))
