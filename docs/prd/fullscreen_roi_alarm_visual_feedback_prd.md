# 全螢幕 ROI 重疊告警動態視覺反饋規格書 (Spec)

## Problem Statement

在目前的 Argus Safety Predictor Nano 架構中，系統已支援每路串流繪製多邊形 ROI（Region of Interest）並於後端產生入侵事件。然而在 Web UI 全螢幕檢視模式（Fullscreen Modal）下，雖然能透過 HTML5 Canvas 疊加顯示青色 ROI 區域與綠色 YOLO 偵測框，但**缺乏即時的重疊告警視覺反饋**：
1. 當偵測物體（如人員、車輛）進入或重疊於 ROI 警戒區域內並符合告警條件時，前端畫面的偵測框依然顯示為一般的終端機綠色（`#00ff41`），無法直觀區分「安全巡檢中」與「入侵警戒觸發」的物體。
2. ROI 多邊形區域在發生入侵時仍保持靜態青色，缺乏動態警戒高亮。
3. 監控人員在遠距離查看全螢幕時，無法第一時間察覺畫面中已觸發特定區域的安全告警。

## Solution

在維持系統既有前後端解耦與極低 CPU 負載（ADR-010、ADR-012）的前提下，由前端 HTML5 Canvas 與全螢幕視窗提供**多層級的即時告警視覺呈現**：
1. **偵測框顏色與樣式動態轉換**：
   - 當物體中心點/底邊落入 ROI 多邊形內部且符合告警標準時，邊界框即刻由終端機綠色轉換為警示紅（`--danger: #ff3333`），線寬增粗（3px），並於標籤加入 `[ALARM]` 警示字樣與深紅半透明底色。
   - 未進入 ROI 之物體維持終端機綠色（`#00ff41`）。
2. **ROI 警戒區域本體動態高亮**：
   - 區域內偵測到違規物體時，多邊形邊框與填充色由預設青色（`rgba(0, 229, 255, 0.15)`）動態切換為紅色半透明（`rgba(255, 51, 51, 0.25)`），標籤顯示為 `[ ROI: <區域名稱> - INTRUSION ]`。
3. **全螢幕介面級警示呼吸燈**：
   - 當當前全螢幕串流存在告警物體時，全螢幕 Modal 視窗四週啟用紅色脈衝內光暈（`box-shadow: inset 0 0 25px rgba(255, 51, 51, 0.6)`），頂部狀態徽章同步切換為閃爍的 `[ ZONE: ALARM TRIGGERED ]`。
4. **極低前端開銷**：
   - 判定計算全數於前端 JavaScript 以射線交叉法（Ray-casting algorithm）進行幾何判斷或由後端輕量標記，零增加樹莓派 CPU 負擔與網路頻寬。

## User Stories

1. As a safety monitoring operator, I want bounding boxes inside the active ROI zone to instantly turn red with an `[ALARM]` tag, so that I can immediately notice safety boundary breaches.
2. As a safety monitoring operator, I want objects outside the ROI zone to remain green, so that I can differentiate normal workplace activities from hazardous incursions.
3. As a plant supervisor observing a remote display screen, I want the entire fullscreen view border to pulse with a subtle red alert glow when an alarm condition is active, so that I can see incidents from a distance without staring at coordinates.
4. As a security officer, I want the ROI zone polygon itself to highlight in translucent red with an `[INTRUSION]` tag when occupied, so that I know exactly which safety boundary was violated.
5. As a system administrator running on Raspberry Pi 5, I want all alarm visual rendering to execute on the client-side browser canvas, so that the edge device CPU utilization does not spike during high-frequency alarm events.
6. As a UI user, I want alarm bounding boxes to respect the sampled status (e.g. dashed red border with `[ALARM][SAMPLED]`) if the inference result is older than 0.15s, so that I maintain awareness of detection freshness during alarms.
7. As a security operator watching a scene with multiple objects, I want each bounding box to be evaluated individually against the ROI, so that an alarm on one person does not falsely color non-intruding workers.
8. As an operator editing an ROI zone, I want alarm highlights to be temporarily suppressed while in zone edit mode, so that I can adjust vertex coordinates without visual interference.
9. As a site technician reviewing cameras without active ROI zones, I want all bounding boxes to display normally in terminal green without false alarm triggers.
10. As a monitoring station user switching between streams, I want the alarm visual state to instantly update according to the selected camera stream's specific ROI and detection state.

## Implementation Decisions

- **Client-Side Spatial Point-in-Polygon Evaluation**:
  - In `drawCanvas()`, for each detected bounding box, compute its bottom-center anchor point $(cx, cy) = ((x_1 + x_2) / 2 \cdot \text{scaleX}, y_2 \cdot \text{scaleY})$ (or center point $(cx, cy)$ normalized to $[0, 1]$).
  - Test intersection against `currentSavedZone.polygon` using standard 2D Ray-Casting algorithm.
- **Dynamic Style Rules (Canvas & DOM)**:
  - **Normal Box**: `ctx.strokeStyle = '#00ff41'`, `lineWidth = 2`, `ctx.fillStyle = 'rgba(0, 59, 0, 0.85)'`.
  - **Alarm Box**: `ctx.strokeStyle = '#ff3333'`, `lineWidth = 3`, `ctx.fillStyle = 'rgba(80, 0, 0, 0.9)'`, Label: `[ALARM] Class <cls> (<conf>%)`.
  - **Alarm Stale Box**: `ctx.setLineDash([5, 5])`, `ctx.strokeStyle = 'rgba(255, 51, 51, 0.8)'`, Label: `[ALARM][SAMPLED] Class <cls> (<conf>%)`.
  - **ROI Polygon Alert**: When `hasAlarmInZone === true`, `ctx.fillStyle = 'rgba(255, 51, 51, 0.25)'`, `ctx.strokeStyle = '#ff3333'`, Tag: `[ ROI: <NAME> - INTRUSION ]`.
  - **Fullscreen Modal CSS Alert**: Toggle CSS class `alarm-active` on `#fullscreen-modal` when `hasAlarmInZone === true` to trigger `box-shadow` CSS pulse animation.
- **Adherence to ADR-010 and ADR-012**:
  - Zero modifications to server-side image encoding or Python OpenCV draw routines.
  - Video stream MJPEG relay remains unthrottled and clean.

## Testing Decisions

- **Good Test Criteria**: Test observable client rendering behavior when detection objects intersect or do not intersect configured ROI polygon boundaries.
- **Seams & Modules Tested**:
  - **Web UI Fullscreen Overlay Seam**: Test that the frontend JavaScript canvas drawing function correctly identifies in-polygon detections and applies alert styles, labels, and CSS modal classes.
  - **Event Feed Data Consistency Seam**: Verify `/detections_feed` SSE endpoint supplies accurate `frame_w`, `frame_h`, `detections`, and `zone` metadata.
- **Prior Art**:
  - `test_sse_detections.py` (SSE payload format and integration)
  - `test_zone_endpoint.py` (ROI polygon API persistence and retrieval)

## Out of Scope

- Audio sound effect alerts or browser Web Audio API alarms.
- Multi-camera simultaneous grid alarm pulsing (only applies to active fullscreen single stream view).
- Multi-polygon compound boolean logic (AND/OR combinations of multiple zones per stream).

## Further Notes

- Maintains 100% visual consistency with the Argus dark industrial/cyberpunk green and cyan design system, utilizing standard CSS variables `--danger: #ff3333` and `--warn: #ffaa00`.
