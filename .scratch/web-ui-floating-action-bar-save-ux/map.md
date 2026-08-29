# Effort: Web UI Floating Action Bar & Dirty State Save UX (Issues #38, #39, #40, #41)

## Notes
實作 Web UI 全域浮動儲存條（Floating Action Bar）、跨面板未儲存狀態標記（Dirty Indicators）、一鍵放棄變更還原機制與無縫 AJAX 非同步儲存與 Toast 通知。

## Decisions so far
- **全域浮動儲存條**：平時隱藏，偵測到任何欄位或串流變更時滑出，固定於畫面底部中央。
- **跨面板未儲存標記**：右側修改串流時，左側對應串流項目標註 `*` 且保留記憶體草稿。
- **一鍵放棄變更**：點擊「放棄變更」將所有全域參數與串流設定還原為初始快照。
- **無縫 AJAX 儲存與 Toast**：透過非同步 Fetch 提交，即時影像串流不中斷，成功後彈出綠色 HUD Toast。

## Map
- [01-backend-ajax-save-support.md](issues/01-backend-ajax-save-support.md) (Issue #38)
- [02-floating-action-bar-ui-and-css.md](issues/02-floating-action-bar-ui-and-css.md) (Issue #39)
- [03-dirty-state-tracking-and-revert.md](issues/03-dirty-state-tracking-and-revert.md) (Issue #40)
- [04-seamless-ajax-save-and-verification.md](issues/04-seamless-ajax-save-and-verification.md) (Issue #41)
