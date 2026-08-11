# ADR-002：使用 ultralytics NCNN 包裝層而非原生 ncnn Python API

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-11 |
| **決策者** | 開發團隊 |
| **相關 PRD** | [ncnn_support_prd.md](../prd/ncnn_support_prd.md) |

---

## 情境與問題

要在系統中加入 NCNN 推論能力，有兩種實作路徑：
1. 使用 `ultralytics` 的 NCNN 包裝（`YOLO('model_ncnn_folder').predict()`）
2. 直接使用原生 `ncnn` Python 套件（`ncnn.Net().load_param()` + 自行寫前後處理與 NMS）

## 決策選項

### 選項 A（已採用）：ultralytics NCNN 包裝層
直接以 `YOLO('best_ncnn_model')` 載入，呼叫 `.predict()` 取得結果，無需額外程式碼。

### 選項 B：原生 ncnn Python API
使用 `ncnn.Net()` 直接操作網路，自行實作：
- Letterbox 前處理
- 模型輸入 `Mat` 建立與正規化
- 輸出張量解析（YOLOv8 特定格式）
- NMS（非極大值抑制）
- 座標還原至原始影像尺寸

## 決策

**採用選項 A（ultralytics 包裝層）。**

## 理由

1. **介面一致性**：PyTorch 與 NCNN 後端共用相同的 `.predict()` 呼叫，`InferenceEngine.infer()` 的對外介面凍結，`main.py` 主迴圈無需任何修改。
2. **大幅降低實作複雜度**：免除自寫 ~100 行的前後處理程式碼，消除座標計算錯誤的風險。
3. **float32 / int8 自動識別**：ultralytics/ncnn 自動偵測 `.bin` 檔的量化格式，兩者在程式碼層面無需區分。
4. **維護成本低**：隨 ultralytics 版本更新即獲得 NCNN 相關修正，不需自行追蹤 NCNN API 變更。

## 取捨與風險

- **版本耦合**：對 ultralytics 版本有隱含依賴；若 ultralytics 終止 NCNN 支援，需切換至原生 API。
- **調試透明度較低**：推論管線內部細節被包裝隱藏，問題排查需仰賴 ultralytics 日誌。
- **緩解措施**：在 `requirements.txt` 固定 `ultralytics>=x.x` 版本範圍，並定期驗證 NCNN 推論結果正確性。
