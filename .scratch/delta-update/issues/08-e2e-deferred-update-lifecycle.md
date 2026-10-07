## Parent

#90 (自動更新功能需求)

## What to build

更新端到端測試鏈 `tests/e2e/test_delta_update_flow.py`，完整覆蓋「下載就緒（活體維持舊版）-> 點擊重啟 (Exit 42) -> 守護腳本呼叫 install.py 置換 -> 喚起新版並通過健康檢查 (Commit) / 異常崩潰自動回滾」的真實端到端閉環，確保 CI 測試全線通過並同步更新藍圖地圖。

## Acceptance criteria

- [ ] 修訂 `tests/e2e/test_delta_update_flow.py`，驗證下載完成後活體檔案依然為舊版，符合 READY_TO_INSTALL 規格
- [ ] 驗證重啟觸發 Exit 42 後，模擬守護腳本執行 `install.py --delta`，活體檔案原子切換為新版並產出 `.patch_bak/`
- [ ] 驗證新版程序啟動偵測到 `.update_in_progress` 進入 HEALTHCHECK，通過 `/api/health` 探針後確立為 COMMITTED
- [ ] 驗證健康檢查失敗或崩潰時觸發 `install.py --rollback` 之秒級還原閉環
- [ ] 同步更新 `.scratch/delta-update/map.md` 藍圖文件，記錄重構決策與驗證結果
- [ ] 確保 `pytest tests/unit/ tests/integration/ tests/e2e/` 全線通過

## Blocked by

- #93 (07 — 重構 UpdateManager 狀態機生命週期遞延置換至 Exit 42 並拔除 delta_updater 程式碼異味)
