# 03 — 前端動態 Canvas 畫框與過時抽樣 UI 提示

**What to build:**
在 templates/index.html 的單路檢視 (openFullscreen) 中，Canvas drawCanvas() 比對 SSE payload 中的 ts 與當前時間。若時間差超過 0.15 秒（過時/抽樣中），畫框切換為虛線邊框並標註 [SAMPLED] 標籤；若收到最新推檢結果時立即切回實線框。

**Blocked by:** 02 — 每路獨立推論抽樣器與 Timestamp 傳遞 (Gitea #5)

**Status:** ready-for-agent

- [ ] 點擊單路串流視窗正確訂閱 SSE /detections_feed 進行 HTML5 Canvas 覆蓋繪圖。
- [ ] 偵測時間戳記 ts 距今超過 0.15 秒時，自動切換為虛線框 (setLineDash([4, 4])) 並繪製 [SAMPLED] 標籤。
- [ ] 收到新推論結果瞬間閃爍切換回實線框 (setLineDash([]))。
