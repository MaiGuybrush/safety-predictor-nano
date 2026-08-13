# 01 — 解耦影像解碼串流與去除 Python 伺服器繪框

**What to build:**
修改 StreamHandler 與 VideoHandler，移除接收與播放影格時的大額 sleep (1.0 / fps_limit)，確保前端 /video_feed 與單路端點能以原生 30 FPS 高流暢度與零延遲播放影片。同時移除 VideoHandler 與 Python 後端的畫面方框標注，讓主畫面 (Grid View) 呈現純淨影像；影片倒帶回到第 0 幀時自動清空該串流之歷史偵測。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] StreamHandler.py 移除 time.sleep(1.0 / self.fps_limit)，改為全速 cap.read() 解碼以清空 OpenCV Buffer。
- [ ] 移除 video_handler.py 中的 cv2.rectangle 與 cv2.putText 方框繪製邏輯。
- [ ] 影片模式在倒帶重置影格位置至 0 時，自動清空 latest_detections 歷史記錄。
