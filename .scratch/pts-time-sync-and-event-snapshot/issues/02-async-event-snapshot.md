# 02 — 非同步事件單次截圖與 Metadata 關聯 (Async Single Event Snapshot & Metadata Linking)

**What to build:**
當偵測目標初次觸發事件（`EventStart`）時，系統自動擷取當前未繪製標註框的原始乾淨訊框（Clean frame），透過非同步背景佇列寫入至 `recordings/{camera_id}/snapshots/{pts:.3f}_{event_ref}.jpg`，避免硬碟 I/O 阻塞推論主線程。在該事件持續期間（`EventFrame`）保持去重不重複截圖；在 `EventStart` 的 JSONL metadata 中記錄相對截圖路徑 `snapshots/{pts:.3f}_{event_ref}.jpg`。事件結束（`EventEnd`）後若再次發生新事件，則能觸發新一次的獨立截圖。

**Blocked by:** 01 — PTS 時間戳提取與 ISO 8601 毫秒日誌記錄 (PTS Ingestion & Millisecond Event Logging)

**Status:** ready-for-agent

- [ ] 擴充 `EventMeta` 資料結構支援 `snapshot_path` 選填欄位，並確保 JSONL 序列化正確包含該欄位。
- [ ] 實作非同步截圖工作佇列（Queue + Background Daemon Worker Thread），確保圖片寫入與主推論解耦。
- [ ] 當事件觸發 `EventStart` 時，將 Clean Frame 與路徑塞入佇列，並於狀態中記錄 `snapshotted = True`。
- [ ] 驗證事件持續期間呼叫 `process_detections` 不會產生重複的截圖寫入任務。
- [ ] 驗證目標消失超逾容忍幀數觸發 `EventEnd` 後狀態重置，後續再次偵測到目標會產生新的 `EventStart` 與全新截圖。
- [ ] 撰寫單元測試覆蓋非同步截圖、去重邏輯與 Metadata 路徑格式驗證。
