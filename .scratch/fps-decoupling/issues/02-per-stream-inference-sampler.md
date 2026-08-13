# 02 — 每路獨立推論抽樣器與 Timestamp 傳遞

**What to build:**
重構 main.py 中的 _inference_worker，維護每路串流獨立的 last_infer_time，依據 fps_limit 時間間隔進行時間點抽檢。將推論完成之 Unix Timestamp (ts) 寫入 web_ui.LATEST_DETECTIONS 欄位中，並經由 SSE /detections_feed 傳遞給前端。

**Blocked by:** 01 — 解耦影像解碼串流與去除 Python 伺服器繪框 (Gitea #4)

**Status:** ready-for-agent

- [ ] _inference_worker 依據每路串流獨立的 fps_limit 時間間隔進行推檢抽樣。
- [ ] LATEST_DETECTIONS 及 SSE payload 包含推論完成時間戳記 (ts: float)。
