# 04 — 端對端整合驗證與測試

**What to build:**
執行 py_compile 語法測試與端對端功能驗證。確認在 fps_limit = 2 下畫面保持 30 FPS 高流暢度且無慢動作、主畫面 (Grid View) 呈現純淨影像無方框、點擊單路 Focus 視窗正確顯示動態 Canvas 框與過時抽樣虛線提示，以及影片倒帶自動清空歷史方框。

**Blocked by:** 03 — 前端動態 Canvas 畫框與過時抽樣 UI 提示 (Gitea #6)

**Status:** ready-for-agent

- [ ] 通過 python -m py_compile 語法編譯測試。
- [ ] 驗證 fps_limit = 2 時串流畫面與推論完全解耦，前端影像保持 30 FPS 極速順暢且無慢動作。
- [ ] 驗證主畫面無框，單路視窗觸發 Canvas 畫框與 [SAMPLED] 虛線提示。
