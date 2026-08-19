# 03 — 前端分頁可見性與使用者閒置自動中斷機制

Type: task
Status: unclaimed
Labels: ready-for-agent, Kind/Feature

## Goal
在 Web UI 前端 (`templates/index.html`) 實作 Page Visibility API 與 User Idle Timeout，在使用者離開分頁或無操作超過 5 分鐘時主動中斷串流並展示省電休眠遮罩，操作時無縫喚醒。

## Details
- `templates/index.html`:
  - 監聽 `visibilitychange` 事件：分頁切至背景時清空 `img.src`，切回時重設 `img.src = '/video_feed?t=' + Date.now()`。
  - 建立 5 分鐘閒置計時器，監聽 `mousemove` / `mousedown` / `keydown` / `touchstart` / `scroll`。
  - 逾時時覆蓋半透明「省電休眠中」UI 提示層，並清空 `img.src`。
  - 喚醒時移除提示層並恢復串流。
