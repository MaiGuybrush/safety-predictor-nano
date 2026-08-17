# 01 — 100vh 滿版 CSS 容器與雙視圖切換 (100vh Viewport Layout & View Mode Toggle)

**What to build:** 
改造 HTML 與 CSS 為 100vh 滿版工控工作台（徹底消除全頁外層 Window 垂直捲軸），建立左側獨立內部滾動容器與右側固定雙層容器，並實現 `[ TOGGLE_CONFIG ]` 在「雙欄設定工作台 (Config View)」與「全版大畫面監控 (Monitor View)」之間的平滑切換。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 設定 `html, body` 為 `height: 100vh; overflow: hidden;`，消除外層 window 捲軸。
- [ ] 調整 `.sys-core` 容器高度為 `calc(100vh - header_height)`，採用 Grid 左右雙欄配置（左側 420px，右側 `1fr`）。
- [ ] 左側面板設置 `height: 100%; overflow-y: auto;`，確保表單內部獨立捲動，不影響右側。
- [ ] 右側面板分為上下兩層容器（右上預覽佔 45%，右下資訊佔 55%）。
- [ ] 實作 `[ TOGGLE_CONFIG ]` 切換：隱藏左側時，右側即時影像平滑擴展為滿版全螢幕監控視圖（顯示底部串流選擇列）。
