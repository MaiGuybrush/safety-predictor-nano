# 02 — Web UI 無訊號佔位 + RTSP 視訊區塊常駐

**What to build:** 讓瀏覽器在 RTSP 模式下也能看到視訊顯示區塊，不再因模式不同而消失。當尚無任何推論畫面可顯示時（例如系統剛啟動、RTSP 串流尚未連線），瀏覽器應顯示「NO SIGNAL」黑底文字佔位畫面，而非空白或無限等待。

**Blocked by:** None — 可立即開始。

**Status:** ready-for-agent

- [ ] `web_ui` 模組在啟動時預先生成一張 640×360 的「NO SIGNAL」黑底文字 JPEG，作為模組級常數儲存。
- [ ] `gen_frames()` 在 `LATEST_FRAME` 為 `None` 時輸出佔位幀，而非空轉等待，使瀏覽器 MJPEG 連線保持活躍並顯示佔位畫面。
- [ ] `index.html` 移除視訊顯示區塊（`<aside class="feed-container">`）外層的 `{% if mode == 'video' %}` 條件，讓 RTSP 與 video 模式皆渲染此區塊。
- [ ] `index.html` 移除 CSS Grid 雙欄 layout 的 Jinja2 `{% if %}` 條件，讓兩種模式皆可觸發側邊視訊欄位的響應式佈局。
- [ ] 在 RTSP 模式下打開瀏覽器，應看到視訊區塊顯示「NO SIGNAL」畫面，而非空白。
- [ ] 切換至 video 模式，原有影片播放功能不受影響。
