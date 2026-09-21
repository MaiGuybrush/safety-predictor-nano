## 決策與成果說明 (Resolution)

本票券已完整彙整 Wayfinder 自動更新藍圖之所有階段決策（Issue 76 ~ 80），產出正式架構決策記錄與實作規格：

1. **正式架構決策記錄 (`docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md`)**：
   - 收斂邊緣端 Raspberry Pi 5 部署與維運痛點，確立整合 App Management API (v9.2.0)。
   - 制定 `--onedir` 發布壓縮包結構、`updates/staging/` 暫存驗證與兩階段目錄原子替換（`rename()`），確保 Linux 動態連結庫替換不崩潰且零資料遺失（嚴格保留 `config.yaml`、`models/`、`logs/`）。
   - 設計雙重自我重啟機制（`run.sh` 守護迴圈 Exit 42 + 備用 Detached `updater_helper.sh`）與雙模式狀態機。
   - 確立 30 秒健康狀態評估窗口（進程存活、`/api/health` 探針、首幀推論）與五步驟自動回滾管線（隔離失敗現場、原子還原備份、喚醒上一版、寫入失敗日誌與 Web UI 告警）。
   - 整合 Cyberpunk 風格 Web UI 呼吸徽章、更新彈窗與 SSE 實時下載解壓進度通道。

2. **完整實作規格書 (`.scratch/auto-update-mechanism/spec.md`)**：
   - 定義 `config.yaml` 之 `auto_update` 設定區塊資料結構與完整預設值。
   - 規範核心模組設計（`AppUpdateClient`、`UpdateManager`、`scripts/install.sh`、`scripts/run.sh`、`web_ui.py`）。
   - 建立涵蓋單元測試、整合測試與 E2E 自動回滾模擬之測試矩陣。

3. **自動化測試與原型驗證**：
   - 相關單元與整合測試全數通過（`tests/unit/test_update_manager.py`, `tests/integration/test_web_ui_update.py` 共 10 passed）。
   - 交付獨立互動原型 HTML：`.scratch/auto-update-mechanism/prototypes/update_modal_prototype.html`。
