# 05 — RTSP 動態多串流管理卡片與影片模式切換 (Dynamic RTSP Stream Cards & Mode Switching)

**What to build:** 
在 RTSP 模式下提供結構化動態卡片列表（可動態「+ 新增串流 / ✕ 刪除」，每路自訂 URL、Label、Camera ID 及可選獨立模型覆蓋），切換為影片模式時平滑切換為影片輸入區，並完成全系統 E2E 整合驗證。

**Blocked by:** 02（結構化 Config 儲存）、03（Web UI 版面結構）、04（UMS 模型選單）

**Status:** ready-for-agent

- [x] 實作運作模式切換互動：選擇「RTSP 多路模式」顯示串流卡片列表，選擇「影片驗證模式」顯示單一影片路徑與鏡頭 ID 輸入區。
- [x] 實作動態串流卡片列表：以 DOM 操作支援動態 `+ 新增串流` 與 `✕ 刪除串流`，每項提供 URL、Label、Camera ID 欄位。
- [x] 每路串流提供「可選獨立模型覆蓋 (Override Model)」切換，可為單一鏡頭指定專屬的 Local 模型路徑或 UMS 模型。
- [x] 表單提交時自動序列化每路串流資訊為標準結構化陣列送出，確保後端儲存完全吻合 schema。
- [x] 執行完整的單元測試套件與 E2E 整合驗證，確保在 RTSP/Video 兩種模式下設定儲存、熱重載、單路全螢幕檢視與心跳回報皆正常運作。
