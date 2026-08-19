# ROI Intersect Mode & Sensitivity Map

## Notes & Decisions
- 後端集中判定架構（Single Source of Truth）：由後端 `event_producer.py` / `main.py` 統一處理 `trigger_mode` 與 `sensitivity` 幾何交集計算，並在推論後賦予 `det["in_zone"] = True/False`。
- 透過 SSE `/detections_feed` 將帶有 `in_zone` 的偵測結果推送給前端。
- 前端 Web UI Canvas 直接依據 `det.in_zone` 渲染紅框與 `[ALARM]` 標記，消除前端 JavaScript 幾何計算重複性。
- Web UI 提供觸發模式（中心點 / 相交重疊）與敏感度滑桿（0% ~ 100%），儲存後後端即時熱重載（Hot Reload）立即生效。

## Tickets
- [01-core-geometry-and-intersect-engine.md](issues/01-core-geometry-and-intersect-engine.md) (Status: resolved)
- [02-config-schema-and-zone-rest-api.md](issues/02-config-schema-and-zone-rest-api.md) (Status: resolved)
- [03-sse-enrichment-and-frontend-alarm.md](issues/03-sse-enrichment-and-frontend-alarm.md) (Status: resolved)
- [04-web-ui-controls-and-verification.md](issues/04-web-ui-controls-and-verification.md) (Status: resolved)
