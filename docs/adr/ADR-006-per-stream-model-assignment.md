# ADR-006：每路 RTSP 串流綁定獨立模型（Per-Stream Model Assignment）

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-12 |
| **決策者** | 開發團隊 |
| **相關 PRD** | [rtsp_multi_stream_display_prd.md](../prd/rtsp_multi_stream_display_prd.md) |

---

## 情境與問題

系統支援多路 RTSP 串流，不同攝影機可能部署於不同場景（如入口偵測、倉儲監控），每個場景所需的偵測模型不同。原始設定格式（`rtsp_streams`：字串列表）僅允許指定 URL，無法為個別串流指派模型，系統只能對所有串流使用同一個全域模型。

---

## 決策選項

### 選項 A（已採用）：Config Schema 遷移，`streams` 物件列表

新增 `streams` 欄位，每個元素為含 `url`、`model`（可選）、`label`（可選）的 dict。`model_path` 全域欄位作為 fallback。

```yaml
streams:
  - url: rtsp://192.168.1.100:554/cam1
    model: model_a.pt
    label: "CAM_01"
  - url: rtsp://192.168.1.101:554/cam2
    model: model_b.pt
    label: "CAM_02"
```

### 選項 B：獨立的 `stream_models` mapping 欄位

保留 `rtsp_streams`（URL 列表），新增 `stream_models` dict 以 URL 為 key 對應模型路徑。URL 與模型分兩處管理，容易不同步。

### 選項 C：在 URL 字串中用特殊語法嵌入模型路徑

如 `rtsp://cam1|model_a.pt`，解析複雜，可讀性差，放棄。

---

## 決策

**採用選項 A（`streams` 物件列表）。**

---

## 理由

1. **語意聚合**：串流的 URL、模型、標籤屬於同一實體的屬性，集中在同一個物件中語意最清晰，維護時一目了然。
2. **可擴展**：物件格式日後易於新增更多 per-stream 屬性（如 FPS 限制、信心度門檻覆蓋），無需再次變更頂層 Schema。
3. **向下相容**：`config_manager.get_stream_configs()` 同時支援舊版 `rtsp_streams` 字串列表，存量設定檔無需遷移即可繼續運作。
4. **可選欄位設計**：`model` 與 `label` 皆為可選，未指定時 fallback 至全域 `model_path`，降低設定複雜度。

---

## 取捨與風險

- **Schema 不相容**：`streams` 是新欄位，舊版 `rtsp_streams` 依然有效。若同時設定兩者，`streams` 優先，`rtsp_streams` 被忽略，需在文件中說明。
- **Engine Cache Key 為字串路徑**：相同模型若以不同路徑字串（相對路徑 vs. 絕對路徑）設定，會視為不同模型各自載入。建議設定檔統一使用相對路徑。
- **UI 表單尚未更新**：Web UI 的串流輸入欄位仍為純文字 textarea（適用舊格式）；`streams` 物件格式目前需直接編輯 `config.yaml`，UI 更新留待後續。
