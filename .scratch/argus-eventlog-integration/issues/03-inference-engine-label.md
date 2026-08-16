Status: done

# 03 — inference_engine.py：補上 label string

**What to build:** `InferenceEngine.infer()` 回傳的每筆 detection 補一個 `label` 欄位，來源是 ultralytics `Results.names`。

**Blocked by:** None — can start immediately

- [x] `infer()` 組裝 `detections` 時新增 `"label": r.names.get(int(box.cls), str(int(box.cls)))`（對照不到時 fallback 用 class id 字串，不讓整包偵測結果因為單一 class 沒名字而掛掉）
- [x] 單元測試（`test_inference_engine.py`）：mock `ultralytics.YOLO`，斷言回傳的 detections 帶正確 `label`；對照不到的 class id 走 fallback（`pytest` 2 passed）

## Comments

- 實作於本次 `/grill-me` session。
