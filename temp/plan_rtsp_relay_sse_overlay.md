# RTSP 直接轉發 + SSE 偵測框前端疊加

## 目標描述

重構 RTSP 模式的顯示與推論管線，實現：

1. **MJPEG Relay（選項A）**：伺服器端不做任何標注，直接將 RTSP 解碼後的原始幀以 JPEG 串流轉發至瀏覽器。目的是確認 RTSP 訊號源是否正常，資源消耗最低。
2. **SSE 偵測事件頻道**：獨立的推論執行緒在背景持續運行 YOLO，每次有新偵測結果時透過 **Server-Sent Events (SSE)** 將 JSON 資料推送到前端（含座標、類別、信心度、原始解析度）。
3. **前端 Canvas 疊加**：瀏覽器用 `<canvas>` 絕對定位覆蓋在 MJPEG `<img>` 上，JavaScript 收到 SSE 事件後依比例縮放座標，即時繪製偵測框。無任何伺服器端圖像合成成本。

---

## User Review Required

> [!IMPORTANT]
> **SSE vs WebSocket 選擇**
>
> 你提到了 WebSocket，這裡建議改用 **Server-Sent Events (SSE)**，原因如下：
> - **零額外依賴**：Flask 原生支援，`requirements.txt` 無需新增套件（WebSocket 需要 `flask-socketio + simple-websocket`）
> - **完全符合需求**：偵測資料只需「伺服器 → 瀏覽器」單向傳輸，SSE 即可
> - **瀏覽器自動重連**：`EventSource` API 內建斷線重連
> - **PyInstaller 打包友善**：不需 async event loop（gevent/eventlet）
>
> 如果你需要雙向通訊（例如前端發指令給伺服器），請告知，改用 WebSocket。

> [!IMPORTANT]
> **多路串流的 Canvas 疊加策略**
>
> 多路串流時，MJPEG `/video_feed` 會合成 Grid（純幀拼接）。Canvas 疊加時需將「原始幀座標」轉換為「Grid 儲存格座標」，前端邏輯較複雜。
>
> 本計劃採取簡化策略：多路串流的偵測結果顯示在影像下方的「偵測事件清單」，而非疊加在 Grid 上。若你需要在 Grid 上精確疊加，請告知。

---

## Open Questions

> [!IMPORTANT]
> 1. **多路串流偵測框顯示方式**：接受「側邊欄事件清單」，還是需要精確疊加在 Grid 各儲存格上？
> 2. **推論頻率**：是否要加 `inference_interval`（每 N 幀推論一次）進一步節省 CPU？例如 `inference_interval: 3` 在 15fps 下等於每 0.2 秒推論一次。
> 3. **影像轉發品質**：JPEG 品質建議設為 85，你是否有特定偏好？

---

## 架構圖

```
RTSP Source
    │
    └→ StreamHandler Thread (per stream)
            │  [Queue size=1, fps_limit]
            │
    ┌───────┴────────────────────────┐
    │                                │
    ▼                                ▼
Relay Loop (main)             Inference Thread (daemon)
  取幀 → JPEG encode           Round-Robin 取幀 → YOLO
  → LATEST_FRAME               → web_ui.LATEST_DETECTIONS
  [~3-5% CPU/stream]           [~80-90% CPU, async]
    │                                │
    ▼                                ▼
Flask /video_feed            Flask /detections_feed
  MJPEG stream                 SSE (text/event-stream)
    │                                │
    └──────────────┬─────────────────┘
                   ▼
              Browser
         ┌────────────────────┐
         │  <img> MJPEG feed  │
         │  <canvas> overlay  │ ← JS EventSource 接收 SSE
         │  偵測事件清單      │ ← 多路串流時顯示於此
         └────────────────────┘
         (Client-side render，零伺服器繪圖成本)
```

---

## 資源消耗對比（Pi 5 單路 1080p RTSP）

| 組件 | 現況（伺服器繪框） | 新架構（前端疊加） |
|------|:-----------------:|:-----------------:|
| RTSP decode | ~0.2 核 | ~0.2 核（不變） |
| YOLO 推論 | ~0.8 核（**阻塞顯示**） | ~0.8 核（獨立執行緒，不阻塞顯示） |
| JPEG encode + annotate | ~0.2 核 | ~0.05 核（不繪框） |
| Grid compose | ~0.1 核 | ~0.05 核（純幀拼接） |
| SSE 推送 | — | <0.01 核（小 JSON，20Hz） |
| Canvas 繪圖 | — | 瀏覽器端，零伺服器成本 |
| **有效顯示 FPS** | **~2–5 fps** | **~15 fps** |
| 偵測框延遲 | 與顯示同步 | ~100–300ms（推論完成後推送） |

---

## Proposed Changes

---

### Component 1：`main.py`

#### [MODIFY] main.py

移除 RTSP 迴圈中的 `annotate_frame` 呼叫，新增 `_inference_worker()` 背景執行緒。

```diff
-from grid_composer import annotate_frame, compose_grid
+from grid_composer import compose_grid

+_inference_running = False

+def _inference_worker(stream_units_ref, config_ref, logger_ref):
+    """背景推論執行緒：不阻塞顯示，結果寫入 web_ui.LATEST_DETECTIONS。"""
+    rr_index = 0
+    while _inference_running:
+        units = stream_units_ref[0]
+        if not units:
+            time.sleep(0.1)
+            continue
+        unit = units[rr_index % len(units)]
+        frame = unit["handler"].get_latest_frame()
+        if frame is not None:
+            h, w = frame.shape[:2]
+            detections, inf_time = unit["engine"].infer(
+                frame, config_ref[0].get("conf_threshold", 0.25))
+            logger_ref[0].add_inference_time(inf_time)
+            if detections:
+                logger_ref[0].log_detection(unit["url"], detections)
+            web_ui.LATEST_DETECTIONS[unit["url"]] = {
+                "stream_url": unit["url"],
+                "stream_index": rr_index % len(units),
+                "label": unit["label"],
+                "detections": detections,
+                "frame_w": w,
+                "frame_h": h,
+                "ts": time.time()
+            }
+        rr_index += 1
```

RTSP 主迴圈改為純 relay（各路取原始幀，合成無標注 Grid）：

```diff
 if mode == 'rtsp' and stream_units:
-    unit = stream_units[rr_index % len(stream_units)]
-    frame = unit["handler"].get_latest_frame()
-    if frame is not None:
-        detections, inf_time = engine.infer(frame, ...)
-        annotated = annotate_frame(frame, detections, ...)
-        latest_frames[url] = annotated
-    rr_index += 1
-    active_frames = [latest_frames[...] for ...]
-    grid_img = compose_grid(active_frames, target_width=640)
-    cv2.imencode('.jpg', grid_img, [quality, 80])
+    for unit in stream_units:
+        frame = unit["handler"].get_latest_frame()
+        if frame is not None:
+            latest_raw_frames[unit["url"]] = frame
+    active_raw = [latest_raw_frames[u["url"]]
+                  for u in stream_units if u["url"] in latest_raw_frames]
+    if active_raw:
+        grid_img = compose_grid(active_raw, target_width=640)
+        if grid_img is not None:
+            ret_enc, buf = cv2.imencode(
+                '.jpg', grid_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
+            if ret_enc:
+                web_ui.LATEST_FRAME = buf.tobytes()
 time.sleep(0.01)
```

---

### Component 2：`web_ui.py`

#### [MODIFY] web_ui.py

新增 `LATEST_DETECTIONS` 全域變數與 `/detections_feed` SSE 端點。

```diff
+import json

 LATEST_FRAME = None
+LATEST_DETECTIONS = {}
 MODEL_INFO = {...}
```

```python
@app.route('/detections_feed')
def detections_feed():
    def generate():
        import time
        last_ts_map = {}
        while True:
            updated = []
            for url, data in list(LATEST_DETECTIONS.items()):
                if data.get("ts") != last_ts_map.get(url):
                    last_ts_map[url] = data["ts"]
                    updated.append(data)
            if updated:
                yield f"data: {json.dumps(updated)}\n\n"
            time.sleep(0.05)   # 20Hz 上限
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )
```

---

### Component 3：`templates/index.html`

#### [MODIFY] templates/index.html

新增 Canvas 疊加層與 SSE EventSource 客戶端。

```diff
+.feed-wrapper { position: relative; display: block; }
+#detection-canvas {
+    position: absolute; top: 0; left: 0;
+    width: 100%; height: 100%;
+    pointer-events: none;
+}
+.detection-list {
+    font-size: 0.75rem; padding: 0.5rem;
+    color: var(--text); border-top: 1px solid var(--border);
+    max-height: 120px; overflow-y: auto;
+}
```

```diff
-<img src="/video_feed" class="cam-feed" alt="Video Feed">
+<div class="feed-wrapper">
+    <img src="/video_feed" class="cam-feed" id="cam-feed-img" alt="Video Feed">
+    <canvas id="detection-canvas"></canvas>
+</div>
+<div class="detection-list" id="detection-list"></div>
```

```javascript
// SSE 偵測事件接收
const detEvt = new EventSource('/detections_feed');
detEvt.onmessage = (e) => {
    const streams = JSON.parse(e.data);
    drawDetections(streams);
    updateDetectionList(streams);
};

function drawDetections(streams) {
    const img = document.getElementById('cam-feed-img');
    const canvas = document.getElementById('detection-canvas');
    if (!img || !canvas) return;
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // 單路串流：直接縮放；多路 Grid：座標按儲存格偏移
    streams.forEach(data => {
        const cols = Math.min(streams.length, 2);
        const rows = Math.ceil(streams.length / cols);
        const cellW = canvas.width / cols;
        const cellH = canvas.height / rows;
        const col = data.stream_index % cols;
        const row = Math.floor(data.stream_index / cols);
        const offsetX = col * cellW;
        const offsetY = row * cellH;
        const scaleX = (streams.length === 1 ? canvas.width : cellW) / (data.frame_w || 1);
        const scaleY = (streams.length === 1 ? canvas.height : cellH) / (data.frame_h || 1);
        data.detections.forEach(det => {
            const coords = Array.isArray(det.xyxy[0]) ? det.xyxy[0] : det.xyxy;
            const [x1, y1, x2, y2] = coords;
            const rx = offsetX + x1 * scaleX;
            const ry = offsetY + y1 * scaleY;
            const rw = (x2 - x1) * scaleX;
            const rh = (y2 - y1) * scaleY;
            ctx.strokeStyle = '#00ff41';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(rx, ry, rw, rh);
            const lbl = `${det.cls} (${det.conf.toFixed(2)})`;
            ctx.font = '11px monospace';
            const tw = ctx.measureText(lbl).width;
            ctx.fillStyle = 'rgba(0,0,0,0.65)';
            ctx.fillRect(rx, ry - 16, tw + 6, 16);
            ctx.fillStyle = '#00ff41';
            ctx.fillText(lbl, rx + 3, ry - 4);
        });
    });
}

function updateDetectionList(streams) {
    const list = document.getElementById('detection-list');
    if (!list) return;
    const items = streams.flatMap(s =>
        s.detections.map(d =>
            `[${s.label || s.stream_url}] ${d.cls} conf:${d.conf.toFixed(2)}`
        )
    );
    list.textContent = items.length ? items.join(' │ ') : '── NO DETECTION ──';
}
```

---

### Component 4：`config.yaml`

#### [MODIFY] config.yaml

```yaml
# 推論間隔（每 N 幀推論一次，1=每幀，3=每三幀）
inference_interval: 1
```

---

## Verification Plan

### Automated Tests

```powershell
python -m unittest discover -p "test_*.py"
```

新增 `test_sse_detections.py`，驗證：
- `web_ui.LATEST_DETECTIONS` 結構正確（含 `frame_w`, `frame_h`, `ts`, `stream_index`）
- 推論執行緒與 relay 迴圈確實解耦（relay 不等推論完成）

### Manual Verification

| 步驟 | 預期結果 |
|------|---------|
| 啟動 `python main.py`，RTSP 模式 | 畫面流暢（≥12fps），不因推論卡頓 |
| 有偵測目標時 | Canvas 出現綠色偵測框，位置對齊影像 |
| DevTools → Network | `/detections_feed` 為 `text/event-stream`，持續收到事件 |
| RTSP 斷線 | 顯示 NO SIGNAL 畫面，Canvas 無殘留框 |
| 切換至 video 模式 | 原有播放與伺服器端繪框功能不受影響 |
