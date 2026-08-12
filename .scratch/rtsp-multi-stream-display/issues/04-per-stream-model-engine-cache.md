# 04 — Per-Stream Model + Engine Instance Cache

**What to build:** 讓每路 RTSP 串流可以在設定中指定各自的偵測模型，系統在啟動時依設定建立「串流 ↔ 模型引擎」的配對關係。當多路串流指定相同模型路徑時，系統自動共用同一個 `InferenceEngine` 實例，避免重複載入模型佔用記憶體。熱重載時，此配對關係與 Engine Cache 會一併重建，只有路徑有變動的模型才重新載入。

**Blocked by:** 01（需要 `get_stream_configs()` 提供標準化的串流設定）、03（需要單路推論渲染已可運作，才能在此基礎上擴展為多模型）。

**Status:** ready-for-agent

- [ ] 系統啟動時，依 `get_stream_configs()` 的結果建立 `stream_units` 列表，每個元素為 `(StreamHandler, InferenceEngine, label)` 三元組。
- [ ] 建立 `stream_units` 時，維護 `engine_cache: dict[str, InferenceEngine]`，以模型路徑為 key；相同路徑的模型只建立一個實例並重用。
- [ ] 設定兩路串流各指定不同模型，確認各自推論結果獨立，不互相干擾。
- [ ] 設定兩路串流指定相同模型路徑，系統記憶體佔用應與單模型單路時相近（可透過系統工具目視確認）。
- [ ] 熱重載（修改 `config.yaml` 的 `streams` 設定）時，`stream_units` 與 `engine_cache` 正確重建，不當機。
- [ ] 熱重載時，路徑未改變的模型不重新載入（可由啟動日誌確認 Engine 建立次數）。
- [ ] 使用舊版 `rtsp_streams` 格式的設定檔，行為與修改前相同（迴歸驗證）。
