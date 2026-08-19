# 01 — 核心幾何判定引擎與相交模式支援 (Core Geometry & Intersect Mode Engine)

**What to build:** 
在後端事件生成核心模組（`event_producer.py`）中實作完整的幾何入侵判定演算法。支援 `trigger_mode="center"`（預設中心點）與 `trigger_mode="intersect"`（多邊形與矩形相交/重疊判定），並支援 `sensitivity` 參數（0.0 ~ 1.0，代表重疊面積比例門檻）。當偵測框碰觸或侵入多邊形警戒區時，精確生成 `EventStart` / `EventFrame` / `EventEnd`。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] `_is_inside_zone(det, polygon, frame_w, frame_h, trigger_mode="center", sensitivity=0.0)` 支援 `intersect` 模式與敏感度計算
- [x] 支援 `sensitivity=0.0`：只要偵測框與多邊形產生幾何相交即判定為 True
- [x] 支援 `sensitivity > 0.0`：計算交集面積比例 $\frac{\text{Area}(\text{Bbox} \cap \text{ROI})}{\text{Area}(\text{Bbox})} \ge \text{sensitivity}$
- [x] `process_detections()` 正確由 zone dict 解析 `trigger_mode` 與 `sensitivity` 並進行事件生命週期管理
- [x] 單元測試 `test_event_producer.py` 完整覆蓋 center 模式、intersect 模式在不同 sensitivity 門檻下的事件觸發

## Answer
在 `event_producer.py` 實作了 Sutherland-Hodgman AABB clipping 與 Shoelace 面積計算演算法，使 `_is_inside_zone()` 與 `process_detections()` 完整支援 `trigger_mode="center" | "intersect"` 及 `sensitivity`（0.0 ~ 1.0 面積比例門檻）。已新增單元測試並全數通過驗證。
