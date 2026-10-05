# 02 — AppUpdateClient API Key 嚴格隔離、全鏈路請求防護與 Web UI 視覺警示

**Parent Issue:** [#87](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/87)

**What to build:**
徹底隔離 App Management API Key 與 UMS API Key，杜絕混用。當未配置金鑰時進入 `api_key_missing` 防護狀態，Client 端嚴格攔截網路請求，`UpdateManager` 跳過定時與開機檢查，後端回傳錯誤提示，Web UI 更新彈窗呈現視覺警示並停用檢查按鈕。

**Blocked by:** 01 — 移除 mock_available 記憶體假資料機制並重構為標準 Client Mock ([#86](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/86))

**Status:** resolved

- [x] `AppUpdateClient` 僅支援 `auto_update.api_key` 與環境變數 `APP_MGR_API_KEY`，徹底移除 `ums_api_key` 與 `UMS_API_KEY` 退避。
- [x] 無金鑰時標記 `self.api_key_missing = True` 並輸出警告日誌 `[AppUpdateClient] 未設定 API KEY 無法進行自動更新`。
- [x] `AppUpdateClient` 於發起請求前檢查，若 `api_key_missing == True` 則直接拋出 `AppUpdatePermanentError`，攔截所有外發 HTTP 請求。
- [x] `UpdateManager` 於金鑰缺失時跳過開機即時檢查（`check_on_startup`）與背景定時輪詢。
- [x] 後端 `/api/update/check` 於金鑰缺失時直接返回 `{"status": "error", "message": "未設定 API KEY，無法進行更新檢查，請至設定頁配置 auto_update.api_key"}`。
- [x] Web UI 前端更新彈窗於金鑰缺失時顯示警示標籤「⚠️ 未配置 API KEY，自動更新已暫停」並停用手動檢查按鈕。
- [x] 單元與整合測試完整驗證金鑰隔離、請求攔截與 UI 警示流程。
