# ADR-007：相同模型路徑共用 InferenceEngine 實例（Engine Instance Cache）

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-12 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-006](ADR-006-per-stream-model-assignment.md) |
| **相關 PRD** | [rtsp_multi_stream_display_prd.md](../prd/rtsp_multi_stream_display_prd.md) |

---

## 情境與問題

引入 per-stream model assignment（ADR-006）後，建立 `stream_units` 時若直接為每路串流各建立一個 `InferenceEngine` 實例，多路串流使用相同模型的典型部署情境下（如 4 路攝影機皆使用 `best.pt`），將會載入 4 份相同模型至記憶體，在 Raspberry Pi 5（4GB RAM）上造成不必要的記憶體壓力。

---

## 決策選項

### 選項 A（已採用）：以模型路徑為 key 的 Engine Cache dict

建立 `engine_cache: dict[str, InferenceEngine]`，建立 `stream_units` 時先查 cache，cache miss 才建立新實例。

### 選項 B：每路串流各自建立 InferenceEngine

最簡單，但記憶體浪費。4 路同模型 → 4 倍 RAM 消耗。

### 選項 C：InferenceEngine 內部實作 class-level singleton

以模型路徑為 key 在 class 內部維護靜態 dict。耦合度高，不利單元測試，亦無法由外部控制生命週期。

---

## 決策

**採用選項 A（外部 Engine Cache dict，在 `main.py` 主控）。**

---

## 理由

1. **記憶體效益最大化**：最常見部署情境（多路同模型）下，記憶體消耗與單路相同，不因串流數增加而線性增長。
2. **Push-down 責任邊界清晰**：Cache 由 `main.py` 管理，`InferenceEngine` 本身不感知是否被共用，保持簡單。
3. **執行緒安全**：Round-Robin 排程保證同一時間只有一路在呼叫 `engine.infer()`，共用 Engine 不存在並發競爭問題（詳見 ADR-008）。
4. **熱重載友好**：重載時重建整個 `engine_cache`，只對路徑有變動的模型重新載入，路徑未變的模型直接複用舊 cache 中的實例。

---

## 取捨與風險

- **Cache Key 為字串**：路徑比對為精確字串比對，相同模型以不同路徑表示（相對/絕對）時視為不同 key，導致重複載入。緩解方式：`get_stream_configs()` 或 cache 建立時統一轉換為絕對路徑（`os.path.abspath()`）。
- **熱重載時舊 Engine 記憶體釋放**：Python GC 會在物件引用歸零時釋放記憶體，熱重載後舊 `engine_cache` 解除引用即可。YOLO 模型在 CPython 下的記憶體釋放行為依賴 `ultralytics` 與底層 PyTorch 的實作，不保證即時釋放。
- **不適用多 Process 場景**：若未來引入多 Process 架構（模型速度差異懸殊時），Engine Cache 的跨 Process 共用需改用共享記憶體或 IPC，屆時本決策需重新評估。
