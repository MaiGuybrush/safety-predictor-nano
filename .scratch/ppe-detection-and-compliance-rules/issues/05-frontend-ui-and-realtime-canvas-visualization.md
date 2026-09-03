# Issue 05: Frontend UI & Real-time Canvas Visualization

Type: task
Status: resolved
Blocked by: 04

## Description
在 Web UI 全螢幕即時監控畫面呈現工安防護狀態：
1. **畫布渲染 (`drawCanvas`)**：
   - 合規物件（完全著裝之人員、三角錐、護欄）以綠框 (`#00e676`) 標示。
   - 違規人員以紅色框閃爍標示，附帶違規標籤（如 `[VIOLATION: Missing Helmet]`）。
   - 阻隔物缺失時在多邊形區域顯示警示文字。
2. **Zone 狀態徽章 (Badge)**：
   - 頂部狀態列動態顯示外部設備狀態與工安合規總結（如 `[MAINTENANCE] 缺少三角錐 | PPE未齊全`）。
3. **SSE Feed 擴充**：
   - `/detections_feed` 支援傳遞 `ppe_status`, `violations`, `compliance_summary`。

## Acceptance Criteria
- 畫布流暢渲染，標註框顏色與告警文字精確對應。
- 支援不同解析度與全螢幕模式。
- 通過前端畫布渲染測試。

## Answer
已完成 Web UI 全螢幕即時工安監控畫布渲染、徽章動態回饋與 SSE 管道擴充：
1. **全螢幕即時畫布渲染 (`drawCanvas`)**：
   - 違規人員：標註鮮紅框 (`#ff1744`)，上方懸浮 `[違規: missing_helmet / missing_vest]` 醒目標籤。
   - 合規人員：標註綠框 (`#00e676`)，上方懸浮 `[合規] person` 標籤。
   - 安全阻隔物與防護器具（`cone`, `guardrail`, `helmet`, `vest`）：標註安全綠框 (`#00e676`)。
   - 缺失安全阻隔物時，在警戒區多邊形下方動態繪製紅底警示橫條 `[ 警告: 缺失安全阻隔物 (cone, guardrail) ]`。
2. **Zone 狀態徽章與全域告警動態樣式 (`updateZoneBadge`)**：
   - 違規時即刻顯示紅字粗體 `警戒區：工安違規 [缺少阻隔物 / 違規項目]`，並觸發全螢幕外框脈衝警示。
   - 完全合規時顯示綠字粗體 `警戒區：工安合規`。
3. **SSE Feed 與測試驗證**：
   - `/detections_feed` 傳遞包含 `compliance_summary`、`ppe` 與 `violations` 之完整資料流。
   - 新增 `tests/test_frontend_canvas_compliance.py` 驗證前端樣板標籤與 SSE Feed 結構；全專案單元測試全數 PASS 通過。
