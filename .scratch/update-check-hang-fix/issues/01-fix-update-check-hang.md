# #89 — 修復網頁檢查最新版本卡死：增加前端輪詢與按鈕復原保護、縮短查詢逾時並補齊 SSE 防緩衝標頭

**Gitea Issue:** [#89](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/89)

**What to build:** 解決在 Web UI 點擊「↻ 檢查最新版本」後畫面永久卡死在「正在向 App Management API 查詢新版本...」以及按鈕變灰無法再操作的問題。前端增加主動輪詢 (Polling) 作為 SSE 雙重保險，並在任何異常與結束狀態下保證解除按鈕鎖定；後端縮短版本清單查詢之逾時時間至快速失敗模式（10 秒內判定），並於 `/api/update/stream` SSE 路由補齊 `Cache-Control: no-cache`、`Connection: keep-alive`、`X-Accel-Buffering: no` 等標頭。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 點擊「↻ 檢查最新版本」後，即便 SSE 通道受阻或斷線，前端輪詢也能在後端檢查完成後（或最多 15 秒內）正確顯示最新狀態，並解除按鈕鎖定。
- [ ] 當遇到網路失敗或後端未設定 API KEY 時，前端彈出提示後按鈕能恢復為可點擊狀態，不會永久 disabled。
- [ ] 若 App Management API 不可達，後端版本查詢在 10 秒內快速判定失敗，不再阻塞數分鐘。
- [ ] `/api/update/stream` 回應帶有 `Cache-Control: no-cache`、`Connection: keep-alive`、`X-Accel-Buffering: no` 等防緩衝標頭。
- [ ] 通過相關單元測試與整合測試。
