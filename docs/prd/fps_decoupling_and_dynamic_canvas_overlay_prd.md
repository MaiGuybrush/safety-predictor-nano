# 高幀率畫面與推論抽樣解耦及動態畫框 PRD (Spec)

## Problem Statement

在目前的實作中，`fps_limit` 參數同時控制了 OpenCV RTSP/影片的讀幀頻率與 YOLO 推論頻率。當使用者將 `fps_limit` 調低（例如設為 2 FPS）時，`StreamHandler` 會在讀幀迴圈中執行 `time.sleep(1.0 / fps_limit)` (0.5 秒)。由於 RTSP 攝影機或影片檔持續以 30 FPS 發送影格，這導致 OpenCV 的內部解碼緩衝區累積大量未處理影格。`cap.read()` 每次僅讀取下一幀舊影格，造成前端畫面出現嚴重「慢動作（1/15 倍速播放）」與無限累積延遲（嚴重偏離 Live 實時畫面）。

此外，舊架構將所有串流的推論方框混合呈現或在後端標注，缺乏「主畫面乾淨純淨」與「僅在點擊特定單路串流時高亮畫框」的動態掌控能力，且缺乏顯式的視覺訊號告知使用者畫框是來自「抽檢結果」還是「當前影格」。

---

## Solution

1. **串流解碼與推論頻率解耦**：
   - RTSP (`StreamHandler`) 與影片 (`VideoHandler`) 保持以原生高幀率 (30 FPS) 無暫停運作，清空 OpenCV 緩衝區，確保前端 `/video_feed` 與 `/video_feed/<stream_id>` 獲得零延遲的高流暢度畫面。
   - 背景推論工作 (`_inference_worker`) 獨立控管每路串流的推檢頻率，僅在時間間隔超過 `1.0 / fps_limit` 時對最新影格觸發 YOLO 推論。

2. **主畫面無框與單路動態畫框**：
   - 主畫面 (Grid View) 與伺服器端影格編碼保持 100% 清潔（無任何 Python 繪製方框）。
   - 當使用者點選特定串流進入單路 Focus 視窗 (Modal) 時，由前端 HTML5 Canvas 訂閱 SSE (`/detections_feed`) 動態畫框。

3. **抽樣過時方框視覺提示 (Stale Signal)**：
   - 當 Canvas 繪製方框時，比對偵測結果時間戳記 `ts` 與當前時間。若時間差大於 0.15 秒（代表該方框為抽檢過渡期舊結果），邊框自動轉換為**虛線框**並加入 `[SAMPLED]` 標籤，明確告知使用者該框為抽檢過度狀態。

---

## User Stories

1. As a security operator, I want the multi-camera grid view to stream smoothly at 30 FPS regardless of the detection sample rate, so that I can monitor live situations without video lag or slow-motion effects.
2. As a system administrator, I want to set `fps_limit` to a low rate (e.g. 2 FPS) to conserve Raspberry Pi CPU resources, without degrading the frontend video display frame rate.
3. As a monitoring station user, I want the main grid view to display raw clean video without bounding boxes, so that I can see unobstructed camera feeds.
4. As a security analyst, I want to click on a specific camera stream to view a fullscreen overlay with bounding boxes, so that I can focus on object detection details for that specific camera.
5. As a UI user, I want a clear visual indicator (dashed box + `[SAMPLED]` label) when a bounding box is from a sampled inference frame rather than the exact current video frame, so that I understand the detection fresh/stale state.
6. As a user watching a looped video stream, I want previous detection bounding boxes to be cleared instantly when the video rewinds to the beginning, so that old object positions are not shown on new frames.

---

## Implementation Decisions

- **Stream Decoding Architecture**:
  - `StreamHandler._capture_frames()` and `VideoHandler._play_video()` run at un-throttled native stream rate (~30 FPS) with a minimal `0.001s` yield sleep to avoid CPU busy-spin while keeping OpenCV decode buffer empty.
- **Inference Scheduling & State**:
  - `_inference_worker()` maintains `last_infer_time` per stream unit. Inference is executed when `now - last_infer_time >= 1.0 / fps_limit`.
  - Detection payload via SSE includes a unix timestamp `ts` indicating when the inference was completed.
- **Rendering & Overlay Split**:
  - All Python-side bounding box drawing code (`cv2.rectangle`, `cv2.putText`) in `video_handler.py` and `grid_composer.py` is removed.
  - Frontend `index.html` modal canvas handles all box rendering.
  - `drawCanvas()` compares `detObj.ts` with current time. If age > 0.15 seconds, `ctx.setLineDash([4, 4])` and append `[SAMPLED]` tag; otherwise `ctx.setLineDash([])` (solid line).
- **Video Rewind Reset**:
  - When `VideoHandler` resets frame position to 0, `self.latest_detections` and `web_ui.LATEST_DETECTIONS` for that stream are emptied immediately.

---

## Testing Decisions

- **Testing Seams**:
  - **Capture Seam**: Test that `StreamHandler.get_latest_frame()` returns fresh frames without accumulation delay when read at 30 FPS.
  - **Inference Seam**: Test that `_inference_worker` respects `fps_limit` interval per stream unit.
  - **Web UI SSE Seam**: Verify `/detections_feed` payload schema includes `ts`, `stream_index`, `frame_w`, `frame_h`, and `detections`.
- **Quality Criteria**:
  - Verify zero slow-motion playback under `fps_limit = 2` setting.
  - Verify canvas dashed box transition when inference rate is low.

---

## Out of Scope

- Multi-object tracking (MOT / ByteTrack) trajectory smoothing.
- Audio alert sound effects on object detection.

---

## Further Notes

This spec corresponds to Architecture Decision Record **ADR-012**.
