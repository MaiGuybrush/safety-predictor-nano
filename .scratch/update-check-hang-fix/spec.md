# Feature Spec: Fix Update Check Hang & Optimize Fast-Fail

## 背景與問題描述
在 Web UI 點擊「↻ 檢查最新版本」後，介面會呈現按鈕禁用變灰且狀態文字停留在「正在向 App Management API 查詢新版本...」，無法恢復。

### 根本原因
1. **前端單向依賴 SSE**：`/api/update/check` 觸發後端背景執行緒後立即返回，前端將狀態設為 `CHECKING` 並禁用按鈕，但前端缺乏 polling 輪詢機制。若瀏覽器 HTTP/1.1 連線數達上限（被 MJPEG 與辨識 SSE 佔用）或 SSE 未能即時推送，前端永久卡死。
2. **錯誤防呆不足**：前端 `triggerCheckUpdate` 發起請求前即將按鈕設為 disabled，但在遇到缺少 API KEY、網路錯誤或 alert 後未將按鈕恢復。
3. **後端查詢逾時過長**：`AppUpdateClient` 單次 timeout 30 秒、重試 3 次，加上 fallback 路徑，在伺服器不可達時會阻塞 3~6 分鐘。
4. **SSE 標頭缺失**：`/api/update/stream` 缺少 `Cache-Control: no-cache`、`Connection: keep-alive`、`X-Accel-Buffering: no`，可能被反向代理或瀏覽器緩衝。

## 解決方案
1. 前端在點擊檢查後啟動週期輪詢 `/api/update/status`（最長 15 秒），當狀態脫離 `CHECKING` 時立即更新畫面並停止輪詢。在任何 error/catch 流程中必定將按鈕恢復為可點擊。
2. 後端在版本檢查呼叫時使用短逾時（5~8 秒），最多重試 1~2 次，確保在不可達時 10 秒內快速退出。
3. `/api/update/stream` 補齊防緩衝標頭。
