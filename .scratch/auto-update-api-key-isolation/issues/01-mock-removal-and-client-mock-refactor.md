# 01 — 移除 mock_available 記憶體假資料機制並重構為標準 Client Mock

**Parent Issue:** [#86](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/86)

**What to build:**
移除 `UpdateManager` 內部的純記憶體假資料區塊與 `mock_available` 參數，使版本檢查一律回歸由 `AppUpdateClient` 統一調度，並將 Web UI 與測試重構為標準 Client Mock 架構。

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] 移除 `UpdateManager.check_for_updates` 內部的純記憶體假資料區塊與 `mock_available` 參數。
- [x] 移除 Web UI 後端 `/api/update/check` 路由與前端模板中的 `mock_available` 參數。
- [x] 重構現有單元與整合測試，改用標準 `unittest.mock` 模擬 Client，移除對內部假資料的依賴。
- [x] 現有更新相關單元與整合測試全數 PASS。
