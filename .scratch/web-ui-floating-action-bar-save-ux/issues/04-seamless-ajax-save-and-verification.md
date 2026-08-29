# Issue #41: 無縫 AJAX 非同步提交整合與端對端驗證

Type: task
Status: resolved

**Role:** resolved

**What to build:**
將前端浮動儲存條之儲存動作與後端 AJAX 路由對接，實現點擊儲存時即時影像串流（MJPEG Feed）完全不中斷、不黑屏閃爍。儲存成功後彈出綠色 HUD Toast「✓ 設定已成功儲存並生效」，清除 Dirty 狀態與串流 `*` 標記並自動收合浮動條；若儲存失敗顯示紅色錯誤 Toast。完成完整的端對端互動測試與驗證。

**Blocked by:**
- Issue #38 (feat: 後端 AJAX 儲存支援與狀態回應)
- Issue #40 (feat: 前端 Dirty State 變更追蹤、串流未儲存標記與一鍵還原)

**Acceptance criteria:**
- [x] 儲存時透過 AJAX 送出，影像串流保持連線不中斷。
- [x] 儲存成功時跳出綠色 HUD Toast 通知，更新內部快照並收合浮動條。
- [x] 儲存失敗時顯示紅色錯誤 Toast 並保持浮動條展開以供修正。
- [x] `config.yaml` 確實寫入最新設定值。
- [x] 通過端對端互動驗證與單元測試。
