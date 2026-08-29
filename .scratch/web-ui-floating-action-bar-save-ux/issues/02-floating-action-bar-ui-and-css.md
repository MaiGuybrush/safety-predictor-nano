# Issue #39: 前端全域浮動儲存條與 Toast UI 元件

Type: task
Status: resolved

**Role:** resolved

**What to build:**
在 `templates/index.html` 建立全域浮動儲存條（Floating Action Bar）與 HUD Toast 通知元件之 HTML 結構與 CSS 動畫，具備賽博龐克暗黑終端美學（深黑背景、終端綠邊框、呼吸微光），支援滑入/滑出動畫與 ADR-016 響應式斷點自適應。

**Blocked by:** None — can start immediately.

**Acceptance criteria:**
- [x] 浮動儲存條置底置中，預設隱藏，加上 `.visible` class 時平滑滑入。
- [x] 浮動儲存條包含「儲存並套用設定」與「放棄變更」兩顆按鈕及狀態說明。
- [x] HUD Toast 元件支援成功與失敗樣式並自動停留 3 秒淡出。
- [x] 在寬螢幕、標準、小螢幕與行動直向各斷點下均能自適應縮放且不溢位破版。
