# 06 — 產出正式架構決策記錄 (ADR-019) 與實作計畫規範

Type: task
Status: resolved
Blocked by: 04, 05

## Question

彙整所有研究、決策與原型成果，撰寫正式的架構決策記錄 `docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md`，並在 `.scratch/auto-update-mechanism/spec.md` 產出完整的實作計畫與驗證清單。

## Scope

1. **架構決策記錄 (ADR-019)**:
   - 記錄上下文、動機、API 整合考量、手動 onedir 目錄原子替換原理、雙模式（自動 vs 提示）選擇、30 秒看門狗回滾策略與安全性權衡。
2. **完整實作規格書 (`spec.md`)**:
   - 資料結構與配置檔定義（`config.yaml` 範本）。
   - 模組設計：
     - `src/argus/integration/app_update_client.py`
     - `src/argus/core/update_manager.py`
     - `scripts/install.sh` 與 `scripts/run.sh`
     - `src/argus/web/web_ui.py` 更新相關端點與前端 UI 實作
   - 測試方案：單元測試、假伺服器 mock API 測試、端到端 (E2E) 升級與自動回滾模擬測試清單。

## Answer

1. **產出正式架構決策記錄 [`docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md`](../../docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md)**：
   - 詳盡記載邊緣端 Raspberry Pi 5 手動部署維運之痛點。
   - 正式收斂 App Management API (v9.2.0) 串接架構與 SemVer 2.0.0 穩定通道篩選機制。
   - 定義 `--onedir` 發布壓縮包目錄結構、Staging 兩階段原子目錄替換 (`rename()`) 原理，保障動態庫替換安全與零資料遺失（嚴格保留 `config.yaml`、`models/`、`logs/`）。
   - 制定雙重自我重啟機制（`run.sh` 守護迴圈 Exit 42 + Detached `updater_helper.sh`）與雙模式狀態機。
   - 確立 30 秒健康狀態評估窗口（進程存活、`/api/health` 探針、首幀推論就緒）與五步驟自動回滾管線（隔離失敗現場、原子還原備份、喚醒上一版本、記錄失敗日誌與 Web UI 告警）。
   - 規範 Web UI Cyberpunk 風格動態呼吸徽章、更新管理彈窗與 SSE 實時下載進度條。

2. **產出權威實作規格書與驗證清單 [`.scratch/auto-update-mechanism/spec.md`](spec.md)**：
   - 完整定義 `config.yaml` 之 `auto_update` 設定區塊資料結構與預設值。
   - 詳細規範 4 大核心模組之類別設計、關鍵方法與責任邊界（`AppUpdateClient`、`UpdateManager`、`scripts/install.sh`、`scripts/run.sh`、`web_ui.py`）。
   - 整理包含單元測試（Client/Manager）、整合測試（Web API/Install Script）與 E2E 自動回滾模擬之完整測試矩陣。

