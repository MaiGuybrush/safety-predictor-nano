Status: done

# 04 — event_producer 核心模組（狀態機）

**What to build:** 新模組 `event_producer.py`，唯一入口 `process_detections(stream_key, camera_id, detections, frame_w, frame_h, severity_map=None, tolerance=2)`。把偵測結果轉成 `argus_eventlog.event_queue` 上的 `EventStart`/`EventFrame`/`EventEnd`。這是整個功能唯一的狀態機 seam，05 只負責呼叫它。

**Blocked by:** 03（detections 需要帶 `label`）

- [x] 模組層級狀態 `_state: {(stream_key, label): {"event_ref": str, "absent": int}}`
- [x] label 首次出現 → 新 `event_ref`（`f"{label}_{YYYYMMDD_HHMMSS_ffffff}"`）→ 依序 `EventStart`（`category=label`、`severity=severity_map.get(label, "warning")`、`meta=EventMeta(roi=[[0,0],[1,0],[1,1],[0,1]])`）+ `EventFrame`
- [x] label 持續出現 → `absent` 歸零，只發 `EventFrame`
- [x] `_state` 裡有但這次沒偵測到的 label → `absent += 1`；超過 `tolerance` 才發 `EventEnd(reason="no_longer_detected")` 並從 `_state` 移除；未超過前保持事件開啟、不發 frame
- [x] bbox 正規化：`x=x1/frame_w`、`y=y1/frame_h`、`w=(x2-x1)/frame_w`、`h=(y2-y1)/frame_h`
- [x] 單元測試（`test_event_producer.py`，比照 `clean_queue` fixture 手法）：出現→持續→消失（含容忍值內/外）、`event_ref` 前後一致、同 stream 兩種 label 互不干擾、severity 覆寫/預設、bbox 正規化 —— 7 個測試全綠

## Comments

- 實作於本次 `/grill-me` session。
