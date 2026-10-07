Status: resolved

## Parent

#90 (自動更新功能需求)

## What to build

更新端到端測試鏈 `tests/e2e/test_delta_update_flow.py`，完整覆蓋「下載就緒（活體維持舊版）-> 點擊重啟 (Exit 42) -> 守護腳本呼叫 install.py 置換 -> 喚起新版並通過健康檢查 (Commit) / 異常崩潰自動回滾」的真實端到端閉環，確保 CI 測試全線通過並同步更新藍圖地圖。

## Acceptance criteria

- [x] 修訂 `tests/e2e/test_delta_update_flow.py`，驗證下載完成後活體檔案依然為舊版，符合 READY_TO_INSTALL 規格
- [x] 驗證重啟觸發 Exit 42 後，模擬守護腳本執行 `install.py --delta`，活體檔案原子切換為新版並產出 `.patch_bak/`
- [x] 驗證新版程序啟動偵測到 `.update_in_progress` 進入 HEALTHCHECK，通過 `/api/health` 探針後確立為 COMMITTED
- [x] 驗證健康檢查失敗或崩潰時觸發 `install.py --rollback` 之秒級還原閉環
- [x] 同步更新 `.scratch/delta-update/map.md` 藍圖文件，記錄重構決策與驗證結果
- [x] 確保 `pytest tests/unit/ tests/integration/ tests/e2e/` 全線通過

## Answer

已完成 `tests/e2e/test_delta_update_flow.py` 的端到端生命週期與回滾閉環重構：
1. 修正 `test_delta_update_full_lifecycle_e2e`：
   - 下載完成至 `READY_TO_INSTALL` 狀態時，活體檔案依然保持舊版本（v1.0.0），嚴格遞延置換至 Exit 42。
   - 觸發 `trigger_restart` 時產生包含完整中繼資料的 `.update_in_progress` 標記檔並觸發 Exit 42。
   - 模擬外層守護腳本（`run.bat` / `run.sh`）捕捉 Exit 42 後執行獨立 `install.py --delta updates/staging`，活體檔案原子切換至新版本（v1.1.0）並產出 `.patch_bak/`。
   - 模擬重啟後之新進程 UpdateManager 偵測到 `.update_in_progress` 自動進入 `HEALTHCHECK`，通過 `/api/health` 探測後確立為 `COMMITTED`，版本更新為 1.1.0 並清除更新標記。
2. 修正 `test_delta_update_healthcheck_failure_auto_rollback`：
   - 模擬更新後異常崩潰或健康檢查失敗時，守護程序執行 `install.py --rollback`。
   - 驗證秒級還原至舊版 `argus.zip`，產生 `.rollback_alert`，重啟後 `/api/health` 回傳 `rollback_occurred: True`。
3. 全線測試通過：unit、integration、e2e 測試 100% 通過。

## Blocked by

- #93 (07 — 重構 UpdateManager 狀態機生命週期遞延置換至 Exit 42 並拔除 delta_updater 程式碼異味)
